import os
import sys
import io
import re
import gc
import zipfile
import pytesseract
import pdfplumber
from PIL import Image
import olefile
import xlrd

from markitdown import (
    MarkItDown,
    DocumentConverter,
    DocumentConverterResult,
    StreamInfo,
    UnsupportedFormatException,
    FileConversionException,
    MissingDependencyException,
)

from core_utils import (
    safe_long_path,
    open_file_with_retry,
    run_with_timeout,
    ConversionPolicyError,
    SUPPORTED_EXTENSIONS,
    IMAGE_EXTENSIONS,
    ZIP_MAX_ENTRIES,
    ZIP_MAX_ENTRY_BYTES,
    ZIP_MAX_TOTAL_BYTES,
    ZIP_MAX_COMPRESSION_RATIO,
    ZIP_MAX_DEPTH,
)

try:
    from gemini_ocr_engine import (
        ocr_image_bytes,
        ocr_pdf_page_bytes,
        GeminiQuotaExhaustedError,
    )
except ImportError:
    ocr_image_bytes = None
    ocr_pdf_page_bytes = None
    GeminiQuotaExhaustedError = RuntimeError

try:
    from ocr_postprocessor import heal_cross_page_continuations, heal_document_markdown
except ImportError:
    heal_cross_page_continuations = lambda pages: pages
    heal_document_markdown = lambda md: md


def configure_tesseract(api):
    """Select an external Tesseract binary before an OCR operation."""
    roots = [
        getattr(api, 'base_dir', ''),
        getattr(api, 'base_dir_exe', ''),
        getattr(api, 'base_dir_meipass', ''),
        os.path.dirname(getattr(api, 'base_dir', '')) if getattr(api, 'base_dir', '') else '',
        os.path.dirname(getattr(api, 'base_dir_exe', '')) if getattr(api, 'base_dir_exe', '') else '',
    ]
    candidates = []
    seen = set()
    for root in roots:
        if not root:
            continue
        for relative in ('src/Tesseract-OCR', 'Tesseract-OCR'):
            tess_root = os.path.join(root, relative)
            if tess_root in seen:
                continue
            seen.add(tess_root)
            candidates.append((
                os.path.join(tess_root, 'tesseract.exe'),
                os.path.join(tess_root, 'tessdata'),
            ))
    candidates.append((r'C:\Program Files\Tesseract-OCR\tesseract.exe', None))
    for tesseract_path, tessdata_path in candidates:
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            if tessdata_path and os.path.exists(tessdata_path):
                os.environ['TESSDATA_PREFIX'] = tessdata_path
            return


class LocalOcrPdfConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext == '.pdf'

    def convert(self, file_stream, stream_info, **kwargs):
        configure_tesseract(self.api)

        pdf_target = None
        if stream_info and stream_info.local_path and os.path.exists(stream_info.local_path):
            pdf_target = stream_info.local_path

        pdf_source = pdf_target
        pdf_bytes = None
        if not pdf_source:
            file_stream.seek(0)
            pdf_bytes = io.BytesIO(file_stream.read())
            pdf_source = pdf_bytes

        pages_text = []
        gemini_quota_exhausted = False
        try:
            with pdfplumber.open(pdf_source) as pdf:
                total_pages = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    if getattr(self.api, '_scan_aborted', False):
                        break
                    if getattr(self.api, '_scan_paused', False):
                        if hasattr(self.api, '_pause_event'):
                            self.api._pause_event.wait()
                        if getattr(self.api, '_scan_aborted', False):
                            break

                    if pdf_target and hasattr(self.api, 'update_task_subprogress'):
                        self.api.update_task_subprogress(
                            pdf_target,
                            fraction=(page_num - 1) / max(1, total_pages),
                            status_text=f"Trang {page_num}/{total_pages}",
                        )

                    text = (page.extract_text() or '').strip()
                    calc_quality = getattr(self.api, '_calculate_ocr_quality_score', None)
                    quality_score = calc_quality(text) if calc_quality else 1.0
                    needs_ocr = (len(text) < 100 or quality_score < 0.35)

                    if needs_ocr:
                        gemini_text = None
                        rendered_img_bytes = None
                        if (
                            not gemini_quota_exhausted
                            and ocr_pdf_page_bytes is not None
                            and getattr(self.api, 'ocr_engine', 'hybrid') in ('hybrid', 'gemini')
                            and getattr(self.api, 'gemini_api_key', None)
                        ):
                            try:
                                page_img = page.to_image(resolution=200)
                                img_bytes = io.BytesIO()
                                rgb_img = page_img.original
                                if rgb_img.mode in ("RGBA", "P", "LA"):
                                    rgb_img = rgb_img.convert("RGB")
                                rgb_img.save(img_bytes, format='JPEG', quality=88)
                                rendered_img_bytes = img_bytes.getvalue()
                                del page_img, rgb_img, img_bytes
                                gemini_text = ocr_pdf_page_bytes(
                                    rendered_img_bytes,
                                    page_num=page_num,
                                    api_key=self.api.gemini_api_key,
                                    model=self.api.gemini_model,
                                    mime_type="image/jpeg",
                                )
                            except GeminiQuotaExhaustedError as q_err:
                                print(f"[Gemini Quota Exhausted] {q_err} -> Chuyển sang Tesseract.")
                                gemini_quota_exhausted = True
                                gemini_text = None
                            except Exception as g_err:
                                print(f"[Gemini OCR PDF fallback to Tesseract] Page {page_num}: {g_err}")
                                gemini_text = None

                        if gemini_text:
                            text = f"<!-- PAGE {page_num} (Gemini AI OCR Mode) -->\n\n{gemini_text}"
                        else:
                            ocr_lock = getattr(self.api, 'ocr_lock', None)
                            if ocr_lock:
                                with ocr_lock:
                                    if rendered_img_bytes is None:
                                        page_img = page.to_image(resolution=200)
                                        img_bytes = io.BytesIO()
                                        rgb_img = page_img.original
                                        if rgb_img.mode in ("RGBA", "P", "LA"):
                                            rgb_img = rgb_img.convert("RGB")
                                        rgb_img.save(img_bytes, format='JPEG', quality=88)
                                        rendered_img_bytes = img_bytes.getvalue()
                                        del page_img, rgb_img, img_bytes
                                    with Image.open(io.BytesIO(rendered_img_bytes)) as image:
                                        text = pytesseract.image_to_string(image, lang='vie+eng').strip()
                            else:
                                if rendered_img_bytes is None:
                                    page_img = page.to_image(resolution=200)
                                    img_bytes = io.BytesIO()
                                    rgb_img = page_img.original
                                    if rgb_img.mode in ("RGBA", "P", "LA"):
                                        rgb_img = rgb_img.convert("RGB")
                                    rgb_img.save(img_bytes, format='JPEG', quality=88)
                                    rendered_img_bytes = img_bytes.getvalue()
                                    del page_img, rgb_img, img_bytes
                                with Image.open(io.BytesIO(rendered_img_bytes)) as image:
                                    text = pytesseract.image_to_string(image, lang='vie+eng').strip()

                            text = f"<!-- PAGE {page_num} (Tesseract OCR Mode) -->\n\n{text}"
                        rendered_img_bytes = None

                    if text:
                        pages_text.append(text)

                    # Safe Chunking: Giải phóng bộ đệm định kỳ mỗi 10 trang
                    if hasattr(page, 'flush_cache'):
                        try:
                            page.flush_cache()
                        except Exception:
                            pass
                    if page_num % 10 == 0:
                        gc.collect()

                    if pdf_target and hasattr(self.api, 'update_task_subprogress'):
                        self.api.update_task_subprogress(
                            pdf_target,
                            fraction=page_num / max(1, total_pages),
                            status_text=f"Trang {page_num}/{total_pages}",
                        )
        except Exception as e:
            return DocumentConverterResult(markdown=f"Error during local OCR: {str(e)}")

        healed_pages = heal_cross_page_continuations(pages_text)
        merged_md = "\n\n".join(healed_pages).strip()
        final_md = heal_document_markdown(merged_md)
        return DocumentConverterResult(markdown=final_md)


class LocalOcrImageConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext in IMAGE_EXTENSIONS

    def convert(self, file_stream, stream_info, **kwargs):
        file_stream.seek(0)
        img_bytes_raw = file_stream.read()
        file_stream.seek(0)

        gemini_text = None
        if (
            ocr_image_bytes is not None
            and getattr(self.api, 'ocr_engine', 'hybrid') in ('hybrid', 'gemini')
            and getattr(self.api, 'gemini_api_key', None)
        ):
            try:
                mime_type = "image/png"
                ext = (stream_info.extension or "").lower()
                if ext in ('.jpg', '.jpeg'):
                    mime_type = "image/jpeg"
                elif ext == '.bmp':
                    mime_type = "image/bmp"
                elif ext in ('.tif', '.tiff'):
                    mime_type = "image/tiff"

                gemini_text = ocr_image_bytes(
                    img_bytes_raw,
                    api_key=self.api.gemini_api_key,
                    model=self.api.gemini_model,
                    mime_type=mime_type,
                )
            except Exception as g_err:
                print(f"[Gemini OCR Image fallback to Tesseract]: {g_err}")
                gemini_text = None

        if gemini_text:
            text = gemini_text
        else:
            configure_tesseract(self.api)
            try:
                ocr_lock = getattr(self.api, 'ocr_lock', None)
                if ocr_lock:
                    with ocr_lock:
                        with Image.open(file_stream) as img:
                            text = pytesseract.image_to_string(img, lang='vie+eng')
                else:
                    with Image.open(file_stream) as img:
                        text = pytesseract.image_to_string(img, lang='vie+eng')
            except Exception as e:
                text = f"Error during local Image OCR: {str(e)}"

        return DocumentConverterResult(markdown=text)


class LocalDocConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext == '.doc'

    def convert(self, file_stream, stream_info, **kwargs):
        pdf_target = None
        if stream_info and stream_info.local_path and os.path.exists(stream_info.local_path):
            pdf_target = stream_info.local_path

        source = pdf_target if pdf_target else file_stream
        if not source:
            return DocumentConverterResult(markdown="")

        try:
            if hasattr(file_stream, "seek"):
                file_stream.seek(0)
            if not olefile.isOleFile(source):
                return DocumentConverterResult(markdown="")

            ole = olefile.OleFileIO(source)
            if not ole.exists('WordDocument'):
                return DocumentConverterResult(markdown="")

            data = ole.openstream('WordDocument').read()
            decoded_utf16 = data.decode('utf-16le', errors='ignore')

            # Khôi phục các ký tự ANSI bị decode nhầm thành UTF-16LE
            restored = []
            valid_bytes = {9, 10, 13} | set(range(32, 256))
            for char in decoded_utf16:
                cp = ord(char)
                if cp > 255:
                    b1 = cp & 0xFF
                    b2 = (cp >> 8) & 0xFF
                    if b1 in valid_bytes and b2 in valid_bytes:
                        restored.append(chr(b1) + chr(b2))
                    else:
                        restored.append(char)
                else:
                    restored.append(char)
            decoded_utf16 = "".join(restored)

            # Chỉ cho phép ký tự tiếng Việt, tiếng Anh và ký tự đặc biệt thông dụng
            vietnamese_and_english_chars = (
                r'[a-zA-Z0-9'
                r'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặ'
                r'ẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
                r'\-–—,.?\/()\'"“”‘’+:;!@#%&*=_ \t\n\r]'
            )
            pattern = re.compile(vietnamese_and_english_chars + r'{4,}')
            matches = pattern.findall(decoded_utf16)
            clean_chunks = [m.strip() for m in matches if m.strip()]
            full_text = "\n\n".join(clean_chunks)

            if len(full_text) < 100:
                decoded_ascii = data.decode('latin-1', errors='ignore')
                matches_ascii = pattern.findall(decoded_ascii)
                clean_ascii = [m.strip() for m in matches_ascii if m.strip()]
                full_text = "\n\n".join(clean_ascii)

            return DocumentConverterResult(markdown=full_text)
        except Exception as e:
            return DocumentConverterResult(markdown=f"Error during local DOC extraction: {str(e)}")


class LocalXlsConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext == '.xls'

    def convert(self, file_stream, stream_info, **kwargs):
        pdf_target = None
        if stream_info and stream_info.local_path and os.path.exists(stream_info.local_path):
            pdf_target = stream_info.local_path

        try:
            if pdf_target:
                workbook = xlrd.open_workbook(pdf_target)
            elif file_stream:
                if hasattr(file_stream, "seek"):
                    file_stream.seek(0)
                workbook = xlrd.open_workbook(file_contents=file_stream.read())
            else:
                return DocumentConverterResult(markdown="")
            md_content = []
            for sheet in workbook.sheets():
                if sheet.nrows == 0:
                    continue
                md_content.append(f"## Sheet: {sheet.name}\n\n")
                for r in range(sheet.nrows):
                    row_values = sheet.row_values(r)
                    row_str_list = []
                    for val in row_values:
                        if val is None:
                            row_str_list.append("")
                        elif isinstance(val, float):
                            if val.is_integer():
                                row_str_list.append(str(int(val)))
                            else:
                                row_str_list.append(str(val))
                        else:
                            row_str_list.append(str(val).strip().replace('\n', ' '))

                    md_content.append("| " + " | ".join(row_str_list) + " |\n")
                    if r == 0:
                        md_content.append("| " + " | ".join(["---"] * len(row_str_list)) + " |\n")
                md_content.append("\n")
            return DocumentConverterResult(markdown="".join(md_content))
        except Exception as e:
            return DocumentConverterResult(markdown=f"Error during local XLS extraction: {str(e)}")


class SafeZipConverter(DocumentConverter):
    """Bounded in-memory ZIP conversion that never extracts into the source tree."""

    def __init__(self, markitdown):
        super().__init__()
        self.markitdown = markitdown

    def accepts(self, file_stream, stream_info, **kwargs):
        return (stream_info.extension or "").lower() == ".zip"

    @staticmethod
    def _validate_member(info):
        name = info.filename.replace("\\", "/")
        parts = [part for part in name.split("/") if part not in ("", ".")]
        if not name or name.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
            raise ConversionPolicyError("unsafe_archive", f"Đường dẫn ZIP không an toàn: {info.filename}")
        if info.flag_bits & 0x1:
            raise ConversionPolicyError("unsafe_archive", f"ZIP mã hóa không được hỗ trợ: {info.filename}")
        if info.file_size > ZIP_MAX_ENTRY_BYTES:
            raise ConversionPolicyError("unsafe_archive", f"Entry ZIP quá lớn: {info.filename}")
        compressed = max(1, info.compress_size)
        if info.file_size / compressed > ZIP_MAX_COMPRESSION_RATIO:
            raise ConversionPolicyError("unsafe_archive", f"Tỷ lệ nén ZIP bất thường: {info.filename}")

    @staticmethod
    def _decode_filename(info):
        name = info.filename
        if not (info.flag_bits & 0x800):
            try:
                raw_bytes = name.encode("cp437")
                for enc in ("utf-8", "windows-1258", "cp1252", sys.getfilesystemencoding()):
                    try:
                        return raw_bytes.decode(enc)
                    except (UnicodeDecodeError, LookupError):
                        continue
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        return name

    def convert(self, file_stream, stream_info, **kwargs):
        depth = int(kwargs.get("_archive_depth", 0))
        if depth >= ZIP_MAX_DEPTH:
            raise ConversionPolicyError("unsafe_archive", "ZIP lồng vượt quá giới hạn an toàn.")

        try:
            archive = zipfile.ZipFile(file_stream, "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise ConversionPolicyError("unsafe_archive", f"ZIP không hợp lệ: {exc}") from exc

        sections = []
        with archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) > ZIP_MAX_ENTRIES:
                raise ConversionPolicyError("unsafe_archive", "ZIP có quá nhiều entry.")
            total_size = sum(info.file_size for info in members)
            if total_size > ZIP_MAX_TOTAL_BYTES:
                raise ConversionPolicyError("unsafe_archive", "Tổng dung lượng giải nén ZIP vượt giới hạn.")

            for info in members:
                self._validate_member(info)
                decoded_name = self._decode_filename(info)
                extension = os.path.splitext(decoded_name)[1].lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    payload = archive.read(info)
                    member_stream = io.BytesIO(payload)
                    member_info = StreamInfo(
                        extension=extension,
                        filename=os.path.basename(decoded_name),
                    )
                    if extension == ".zip":
                        result = self.convert(
                            member_stream,
                            member_info,
                            _archive_depth=depth + 1,
                        )
                    else:
                        result = self.markitdown.convert_stream(
                            member_stream,
                            stream_info=member_info,
                            _archive_depth=depth + 1,
                        )
                    content = (result.text_content or "").strip()
                    if content:
                        sections.append(f"## File: {decoded_name}\n\n{content}")
                except ConversionPolicyError:
                    raise
                except (UnsupportedFormatException, FileConversionException, MissingDependencyException):
                    continue

        title = stream_info.filename or stream_info.local_path or "archive.zip"
        if not sections:
            raise ConversionPolicyError("conversion_failed", "ZIP không chứa tài liệu hỗ trợ có nội dung.")
        return DocumentConverterResult(markdown=f"# ZIP: {title}\n\n" + "\n\n".join(sections))


def create_markdown_converter(api):
    """Factory creating and configuring MarkItDown with local document converters."""
    c = MarkItDown()
    c.register_converter(LocalOcrPdfConverter(api), priority=-1.0)
    c.register_converter(LocalOcrImageConverter(api), priority=-1.0)
    c.register_converter(LocalDocConverter(api), priority=-1.0)
    c.register_converter(LocalXlsConverter(api), priority=-1.0)
    return c
