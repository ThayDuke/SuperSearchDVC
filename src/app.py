import os
import sys
import hashlib

# Thêm đường dẫn Lib vào sys.path để nạp thư viện ngoài cục bộ
if getattr(sys, 'frozen', False):
    _exe_root = os.path.dirname(os.path.abspath(sys.executable))
    _bundle_root = getattr(sys, '_MEIPASS', _exe_root)
    lib_candidates = [os.path.join(_bundle_root, 'src', 'Lib'), os.path.join(_exe_root, 'src', 'Lib')]
    lib_dir = next((candidate for candidate in lib_candidates if os.path.isdir(candidate)), lib_candidates[0])
    if hasattr(sys, '_MEIPASS'):
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(sys._MEIPASS)
            except Exception:
                pass
        os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
else:
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Lib')

if os.path.exists(lib_dir) and lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

import webview
import subprocess
import re
import json
import shutil
import ctypes
import threading
from concurrent.futures import ThreadPoolExecutor

# Import pandas tslibs first to work around circular import of C APIs in frozen environment
try:
    import pandas._libs.tslibs.np_datetime
except Exception:
    pass

import io
import importlib.util
import zipfile
from importlib.metadata import version as package_version
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
import unicodedata
from index_store import IndexStore


LOCAL_CORE_FORMAT_GROUPS = {
    "documents": (
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx",
        ".html", ".htm", ".epub", ".ipynb", ".msg",
    ),
    "text": (
        ".md", ".markdown", ".txt", ".text", ".json", ".jsonl",
        ".csv", ".xml", ".rss", ".atom",
    ),
    "images": (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"),
    "archives": (".zip",),
}
SUPPORTED_EXTENSIONS = frozenset(
    extension
    for extensions in LOCAL_CORE_FORMAT_GROUPS.values()
    for extension in extensions
)
IMAGE_EXTENSIONS = frozenset(LOCAL_CORE_FORMAT_GROUPS["images"])
FORMAT_DEPENDENCIES = {
    ".pdf": ("pdfplumber", "pytesseract", "PIL"),
    ".doc": ("olefile",),
    ".docx": ("mammoth", "lxml"),
    ".xls": ("xlrd",),
    ".xlsx": ("pandas", "openpyxl"),
    ".pptx": ("pptx",),
    ".msg": ("olefile",),
    ".png": ("pytesseract", "PIL"),
    ".jpg": ("pytesseract", "PIL"),
    ".jpeg": ("pytesseract", "PIL"),
    ".bmp": ("pytesseract", "PIL"),
    ".tif": ("pytesseract", "PIL"),
    ".tiff": ("pytesseract", "PIL"),
}
DEFAULT_SOURCE_LIMIT_BYTES = 512 * 1024 * 1024
IMAGE_SOURCE_LIMIT_BYTES = 100 * 1024 * 1024
ZIP_SOURCE_LIMIT_BYTES = 256 * 1024 * 1024
ZIP_MAX_ENTRIES = 500
ZIP_MAX_ENTRY_BYTES = 100 * 1024 * 1024
ZIP_MAX_TOTAL_BYTES = 500 * 1024 * 1024
ZIP_MAX_COMPRESSION_RATIO = 200
ZIP_MAX_DEPTH = 3


class ConversionPolicyError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def remove_diacritics(text):
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    no_marks = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    cleaned = no_marks.replace('đ', 'd').replace('Đ', 'D')
    return cleaned.lower()


def configure_tesseract(api):
    """Select an external Tesseract binary before an OCR operation."""
    roots = [
        api.base_dir,
        api.base_dir_exe,
        api.base_dir_meipass,
        os.path.dirname(api.base_dir),
        os.path.dirname(api.base_dir_exe),
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
        try:
            with pdfplumber.open(pdf_source) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if self.api._scan_aborted:
                        break
                    if self.api._scan_paused:
                        self.api._pause_event.wait()
                        if self.api._scan_aborted:
                            break

                    text = (page.extract_text() or '').strip()
                    needs_ocr = (
                        len(text) < 100 or
                        self.api._calculate_ocr_quality_score(text) < 0.35
                    )
                    if needs_ocr:
                        with self.api.ocr_lock:
                            page_img = page.to_image(resolution=150)
                            img_bytes = io.BytesIO()
                            page_img.original.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            with Image.open(img_bytes) as image:
                                text = pytesseract.image_to_string(image, lang='vie+eng').strip()
                        text = f"<!-- PAGE {page_num} (OCR Mode) -->\n\n{text}"
                    if text:
                        pages_text.append(text)
        except Exception as e:
            return DocumentConverterResult(markdown=f"Error during local OCR: {str(e)}")

        return DocumentConverterResult(markdown="\n\n".join(pages_text).strip())

class LocalOcrImageConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext in IMAGE_EXTENSIONS

    def convert(self, file_stream, stream_info, **kwargs):
        configure_tesseract(self.api)

        file_stream.seek(0)
        try:
            with self.api.ocr_lock:
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
        
        if not pdf_target:
            return DocumentConverterResult(markdown="")
        
        if not olefile.isOleFile(pdf_target):
            return DocumentConverterResult(markdown="")
        
        try:
            ole = olefile.OleFileIO(pdf_target)
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
            
            # Chỉ cho phép ký tự tiếng Việt, tiếng Anh và ký tự đặc biệt thông dụng, loại bỏ tiếng Trung CJK hoàn toàn
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
            
        if not pdf_target:
            return DocumentConverterResult(markdown="")
            
        try:
            workbook = xlrd.open_workbook(pdf_target)
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
                extension = os.path.splitext(info.filename)[1].lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    payload = archive.read(info)
                    member_stream = io.BytesIO(payload)
                    member_info = StreamInfo(
                        extension=extension,
                        filename=os.path.basename(info.filename),
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
                        sections.append(f"## File: {info.filename}\n\n{content}")
                except ConversionPolicyError:
                    raise
                except (UnsupportedFormatException, FileConversionException, MissingDependencyException):
                    continue

        title = stream_info.filename or stream_info.local_path or "archive.zip"
        if not sections:
            raise ConversionPolicyError("conversion_failed", "ZIP không chứa tài liệu hỗ trợ có nội dung.")
        return DocumentConverterResult(markdown=f"# ZIP: {title}\n\n" + "\n\n".join(sections))

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

class Api:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        if getattr(sys, 'frozen', False):
            self.base_dir_exe = os.path.dirname(sys.executable)
            self.base_dir_meipass = sys._MEIPASS
        else:
            self.base_dir_exe = os.path.dirname(os.path.abspath(__file__))
            self.base_dir_meipass = self.base_dir_exe
        self.runtime_dir = os.path.join(self.base_dir, 'runtime')
        self.runtime_markdown_root = os.path.join(self.runtime_dir, 'MARKDOWN')
        self.runtime_search_db = os.path.join(self.runtime_dir, 'search_db.js')
        self.runtime_index_db = os.path.join(self.runtime_dir, 'supersearch.db')
        self.runtime_status_file = os.path.join(self.runtime_dir, 'index_status.json')
        self.runtime_config_file = os.path.join(self.runtime_dir, 'config.json')
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.index_store = IndexStore(self.runtime_index_db)
        self._migrate_legacy_index()
        self._window = None
        self.active_files = []
        self.lock = threading.Lock()
        self.scan_dir = None
        self.load_saved_folder()
        self._scan_paused = False
        self._scan_aborted = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self.executor = None
        self.ocr_lock = threading.Lock()

    def set_window(self, window):
        self._window = window

    def _migrate_legacy_index(self):
        """Import a legacy JSON search_db without executing JavaScript."""
        if self.index_store.count_documents() > 0:
            return
        legacy_path = os.path.join(self.base_dir, 'data', 'search_db.js')
        if not os.path.exists(legacy_path):
            return
        try:
            with open(legacy_path, 'r', encoding='utf-8', errors='strict') as f:
                source = f.read()
            marker = source.find('=')
            if marker < 0:
                return
            payload = source[marker + 1:].strip().rstrip(';').strip()
            entries = json.loads(payload)
            if not isinstance(entries, list):
                return
            for entry in entries:
                original = entry.get('absolute_original_path') or entry.get('original_path') or ''
                entry['scan_id'] = entry.get('scan_id') or self._scan_id(os.path.dirname(original) or self.base_dir)
            self.index_store.replace_entries(entries)
            output_tmp = f"{self.runtime_search_db}.tmp-{os.getpid()}"
            with open(output_tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(f"var SEARCH_DB = {json.dumps(entries, ensure_ascii=False, indent=2)};\n")
            os.replace(output_tmp, self.runtime_search_db)
            print(f"Migrated {len(entries)} legacy index entries to SQLite")
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"Legacy index migration skipped: {exc}")

    def load_saved_folder(self):
        try:
            path = ''
            if os.path.exists(self.runtime_config_file):
                with open(self.runtime_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    path = str(config.get('scan_dir') or '').strip()
            if not path:
                legacy_file = os.path.join(self.base_dir, 'data', 'folder_path.txt')
                if os.path.exists(legacy_file):
                    with open(legacy_file, 'r', encoding='utf-8') as f:
                        path = f.read().strip()
            if path and os.path.isdir(path):
                self.scan_dir = os.path.normpath(path)
        except Exception as e:
            print(f"Error loading scan_dir: {e}")

    def save_saved_folder(self, path):
        try:
            os.makedirs(self.runtime_dir, exist_ok=True)
            temp_path = self.runtime_config_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump({'scan_dir': path.strip()}, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.runtime_config_file)
            self.scan_dir = os.path.normpath(path)
            return True
        except Exception as e:
            print(f"Error saving scan_dir: {e}")
            return False

    def _scan_id(self, folder_path):
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(folder_path)))
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]

    def _cache_path(self, directory, source_path):
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(source_path)))
        identity = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        return os.path.join(directory, f"{os.path.basename(source_path)}.{identity}.md")

    def _managed_source_dirs(self, scan_target):
        if os.path.normcase(os.path.normpath(os.path.abspath(scan_target))) != os.path.normcase(os.path.normpath(os.path.abspath(self.base_dir))):
            return set()
        return {
            os.path.normcase(os.path.normpath(os.path.abspath(path)))
            for path in (
                self.runtime_dir,
                os.path.join(self.base_dir, 'data'),
                os.path.join(self.base_dir, 'docs'),
                os.path.join(self.base_dir, 'logs'),
                os.path.join(self.base_dir, 'src'),
                os.path.join(self.base_dir, 'MARKDOWN'),
            )
        }

    def _should_skip_source_dir(self, scan_target, path, managed_dirs):
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(path)))
        if normalized in managed_dirs:
            return True
        return os.path.basename(normalized).lower() in {'.git', '.gemini', '.agents', '.vscode', '__pycache__', 'node_modules'}

    def check_folder_status(self, folder_path=None):
        try:
            if not folder_path:
                folder_path = self.scan_dir if self.scan_dir else self.base_dir
            normalized_path = os.path.normcase(os.path.normpath(os.path.abspath(folder_path)))
            
            status_file = self.runtime_status_file
            if os.path.exists(status_file):
                with open(status_file, 'r', encoding='utf-8') as f:
                    scanned_dict = json.load(f)
                if normalized_path in scanned_dict:
                    return {"scanned": True, "total_entries": scanned_dict[normalized_path]}

            # Read legacy status once during migration, without writing it back.
            legacy_file = os.path.join(self.base_dir, 'data', 'SSFolder.txt')
            if os.path.exists(legacy_file):
                with open(legacy_file, 'r', encoding='utf-8') as f:
                    scanned_dict = json.loads(f.read().strip() or '{}')
                if normalized_path in scanned_dict:
                    return {"scanned": True, "total_entries": scanned_dict[normalized_path]}
            return {"scanned": False}
        except Exception as e:
            print(f"Error checking folder status: {e}")
            return {"scanned": False, "error": str(e)}

    def pause_scan(self):
        self._scan_paused = True
        self._pause_event.clear()
        return {"success": True}

    def resume_scan(self):
        self._scan_paused = False
        self._pause_event.set()
        return {"success": True}

    def abort_scan(self):
        self._scan_aborted = True
        self._pause_event.set()
        if self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
        return {"success": True}

    def select_folder(self):
        if self._window:
            result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                selected_dir = os.path.normpath(result[0])
                if not self.save_saved_folder(selected_dir):
                    return {"success": False, "error": "Không thể lưu cấu hình thư mục"}
                status = self.check_folder_status(selected_dir)
                return {
                    "success": True,
                    "folder_path": selected_dir,
                    "scanned": status.get("scanned", False),
                    "total_entries": status.get("total_entries", 0)
                }
        return {"success": False, "error": "Đã hủy chọn thư mục"}

    def set_manual_folder(self, path):
        if not path or not os.path.isdir(path):
            return {"success": False, "error": f"Đường dẫn không hợp lệ hoặc không tồn tại: {path}"}
        
        selected_dir = os.path.normpath(path)
        if not self.save_saved_folder(selected_dir):
            return {"success": False, "error": "Không thể lưu cấu hình thư mục"}
        status = self.check_folder_status(selected_dir)
        return {
            "success": True,
            "folder_path": selected_dir,
            "scanned": status.get("scanned", False),
            "total_entries": status.get("total_entries", 0)
        }

    def get_scan_folder(self):
        return {
            "folder_path": self.scan_dir if self.scan_dir else "",
            "base_dir": self.base_dir
        }

    def get_system_ram_load(self):
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.dwMemoryLoad
        except Exception:
            return 50 # fallback safe value if ctypes fails

    def get_safe_workers_count(self):
        try:
            cpu_cores = os.cpu_count() or 4
            max_cpu_workers = max(1, int(cpu_cores * 0.7))
            ram_load = self.get_system_ram_load()
            if ram_load > 70:
                return 1
            return max_cpu_workers
        except Exception:
            return 2 # fallback

    def search_documents(self, query='', page=1, page_size=50, filters=None):
        return self.index_store.search_documents(query, page, page_size, filters)

    def get_document(self, document_id):
        return self.index_store.get_document(document_id)

    def get_search_vocabulary(self):
        return self.index_store.vocabulary()

    def get_index_stats(self):
        return self.index_store.stats()

    def get_supported_formats(self):
        groups = []
        enabled_extensions = []
        for group_name, extensions in LOCAL_CORE_FORMAT_GROUPS.items():
            items = []
            for extension in extensions:
                missing = []
                for dependency in FORMAT_DEPENDENCIES.get(extension, ()):
                    try:
                        available = importlib.util.find_spec(dependency) is not None
                    except (ImportError, ModuleNotFoundError, ValueError):
                        available = False
                    if not available:
                        missing.append(dependency)
                items.append({
                    "extension": extension.lstrip('.').upper(),
                    "available": not missing,
                    "missing_dependencies": missing,
                })
                if not missing:
                    enabled_extensions.append(extension.lstrip('.').upper())
            groups.append({"name": group_name, "formats": items})
        try:
            markitdown_version = package_version("markitdown")
        except Exception:
            markitdown_version = "unknown"
        return {
            "profile": "LOCAL_CORE",
            "markitdown_version": markitdown_version,
            "groups": groups,
            "enabled_extensions": enabled_extensions,
            "optional_profiles": {
                "network": {"enabled": False, "formats": ["WAV", "MP3", "M4A", "MP4", "URL"]},
                "cloud": {"enabled": False, "formats": ["AZURE", "LLM", "PLUGIN"]},
            },
        }

    def _report_progress(self, percent, active_list):
        if self._window:
            try:
                files_json = json.dumps(active_list)
                self._window.evaluate_js(f"if (window.updateScanProgress) {{ window.updateScanProgress({percent}, {files_json}); }}")
            except Exception as e:
                print(f"Error evaluating progress JS: {e}")

    def open_explorer(self, path):
        # Chuẩn hóa đường dẫn cho Windows
        path = os.path.normpath(path)
        if not self.index_store.is_known_path(path):
            return False
        if os.path.exists(path):
            # Mở Windows Explorer và chọn file
            subprocess.run(["explorer.exe", "/select,", path], check=False)
            return True
        else:
            # Nếu file không tồn tại, thử mở thư mục cha
            parent = os.path.dirname(path)
            if os.path.exists(parent):
                subprocess.run(["explorer.exe", parent], check=False)
                return True
        return False

    def _clean_content(self, content):
        content = re.sub(r'<!--\s*ORIGINAL_PATH:.*?\s*-->', '', content)
        content = re.sub(r'<!--\s*SCAN_TARGET:.*?\s*-->', '', content)
        content = re.sub(r'<!--\s*SOURCE_SIZE:.*?\s*-->', '', content)
        content = re.sub(r'<!--\s*SOURCE_MTIME_NS:.*?\s*-->', '', content)
        content = re.sub(r'<!--\s*SOURCE_SHA256:.*?\s*-->', '', content)
        content = re.sub(r'^#\s*Converted\s+from\s+.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'<!--\s*PAGE\s+\d+\s+\([^)]*\)\s*-->', '', content)
        content = re.sub(r'<!--\s*PAGE\s+\d+\s*-->', '', content)
        content = re.sub(r'!\[[^\]]*\]\(data:image/[^)]*\)', '', content)
        content = re.sub(r'data:image/[^\s)"\'\>]+', '', content)
        content = re.sub(r'[ \t]+', ' ', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content.strip()

    def _is_ocr_noise(self, text):
        total_len = len(text)
        if total_len == 0:
            return True
        pipes = text.count('|')
        symbols = len(re.findall(r'[^a-zA-Z0-9\sÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ]', text))
        words = re.findall(r'\w+', text)
        symbol_ratio = symbols / total_len if total_len else 1
        if len(words) < 4 and (pipes > 8 or symbol_ratio > 0.6):
            return True
        return False

    def _infer_original_ext(self, path):
        name = os.path.basename(path)
        if name.lower().endswith('.md'):
            name = name[:-3]
        return os.path.splitext(name)[1].lower()

    def _calculate_ocr_quality_score(self, text):
        text = text or ""
        tokens = re.findall(r"[A-Za-zÀ-ỹĐđ0-9]{2,}", text)
        if not tokens:
            return 0.0
        # OCR noise is characterized by replacement characters, isolated symbols,
        # and a high ratio of non-word characters.  Do not validate tokens against
        # the same regex that produced them; that made the old score nearly always 1.
        replacement_penalty = min(0.45, text.count(chr(0xfffd)) / max(1, len(text)) * 3.0)
        symbol_count = len(re.findall(r"[^A-Za-zÀ-ỹĐđ0-9\s.,;:!?()/\\\-\[\]_%]", text))
        symbol_penalty = min(0.35, symbol_count / max(1, len(text)) * 1.5)
        short_token_penalty = min(0.35, sum(len(token) <= 2 for token in tokens) / max(1, len(tokens)) * 0.35)
        diversity_penalty = 0.0
        if len(text) >= 40:
            diversity = len(set(text.lower())) / max(1, len(text))
            diversity_penalty = min(0.45, max(0.0, 0.25 - diversity) * 2.0)
        word_signal = min(1.0, len(tokens) / max(1.0, len(text.split()) * 0.75))
        score = word_signal - replacement_penalty - symbol_penalty - short_token_penalty - diversity_penalty
        return round(max(0.0, min(1.0, score)), 3)

    def _classify_source(self, filepath, rel_path, content, ocr_quality_score):
        ext = self._infer_original_ext(filepath)
        content_lower = (content or "").lower()
        rel_lower = (rel_path or "").lower()

        if ocr_quality_score < 0.35:
            return "low_confidence_ocr"

        if ext in SUPPORTED_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
            return "formal_document"

        if ext in IMAGE_EXTENSIONS:
            chat_patterns = [
                r'\b\d{1,2}:\d{2}\b', r'\b(am|pm)\b', 'tin nhắn',
                'đã gửi', 'hôm qua', 'hôm nay', 'chúc mừng', 'sinh nhật',
                'tăng lương', '7tr', 'triệu'
            ]
            if any(re.search(pattern, content_lower) for pattern in chat_patterns):
                return "chat_screenshot"

            ui_patterns = [
                r'\b(import|const|let|function|class)\s+\w+',
                r'</?(div|html|body|script|style)\b',
                r'\b(css|javascript|python|terminal|explorer|workspace)\b',
                r'\.(html|css|js|py|md)\b'
            ]
            if any(re.search(pattern, content_lower) for pattern in ui_patterns) or "screenshot" in rel_lower:
                return "ui_screenshot"

            return "image_ocr"

        return "formal_document"

    def _classify_file(self, filepath, relative_path):
        try:
            size = os.path.getsize(filepath)
        except Exception:
            return "Unknown", 0, "", "", ""

        if size == 0:
            return "Empty/Near Empty", size, "", "", ""

        content = ""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            try:
                with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return "Error Reading", size, "", "", ""

        orig_match = re.search(r'<!--\s*ORIGINAL_PATH:\s*(.*?)\s*-->', content)
        header_orig_path = orig_match.group(1).strip() if orig_match else ""
        target_match = re.search(r'<!--\s*SCAN_TARGET:\s*(.*?)\s*-->', content)
        header_scan_target = target_match.group(1).strip() if target_match else ""

        stripped_content = content.strip()
        if not stripped_content:
            return "Empty/Near Empty", size, "", header_orig_path, header_scan_target

        cleaned = self._clean_content(stripped_content)
        
        generic_phrases = [
            "cict administration documents",
            "hệ thống văn bản quản lý cict",
            "loading/unloading procedure at cict",
            "cict procedure manual",
            "hệ thống kpi cict",
            "cict kpi system"
        ]
        
        is_generic_cover = False
        cleaned_lower = cleaned.lower()
        if len(cleaned) < 120:
            for phrase in generic_phrases:
                if phrase in cleaned_lower:
                    is_generic_cover = True
                    break

        ext = self._infer_original_ext(header_orig_path or relative_path)
        is_image_ocr = ext in IMAGE_EXTENSIONS
        words = re.findall(r'\w+', cleaned)
        word_count = len(words)

        if "error during local" in cleaned.lower() or "error reading" in cleaned.lower():
            return "Error Reading", size, cleaned, header_orig_path, header_scan_target

        if is_image_ocr:
            if len(cleaned) < 20 or word_count < 3 or is_generic_cover:
                return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target
        elif len(cleaned) < 50 or is_generic_cover:
            return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target

        if self._is_ocr_noise(cleaned):
            return "Empty/Near Empty", size, cleaned, header_orig_path, header_scan_target

        underscores = len(re.findall(r'_{3,}', cleaned))
        dots = len(re.findall(r'\.{3,}', cleaned))
        checkboxes = len(re.findall(r'\[\s*\]', cleaned))
        
        placeholders = [
            r'\[tên[^\]]*\]', r'\[ngày[^\]]*\]', r'\[họ\s+và\s+tên[^\]]*\]',
            r'\[địa\s+chỉ[^\]]*\]', r'\[chức\s+vụ[^\]]*\]',
            r'\(ký,\s*ghi\s*rõ\s*họ\s*tên\)', r'\(ký\s*tên\)', r'\(nếu\s*có\)',
            r'dd/mm/yyyy', r'ngày\s+\.\.\.\s+tháng\s+\.\.\.\s+năm\s+\.\.\.\.',
            r'ngày\s+___\s+tháng\s+___\s+năm\s+___',
            r'ông/bà\s+__+', r'họ\s+tên\s*:\s*__+', r'mã\s+số\s*:\s*__+'
        ]
        
        placeholder_count = 0
        for p in placeholders:
            matches = re.findall(p, cleaned, re.IGNORECASE)
            if matches:
                placeholder_count += len(matches)

        total_placeholders = underscores + dots + checkboxes + placeholder_count
        density = total_placeholders / word_count if word_count > 0 else 0
        
        rel_path_lower = relative_path.lower()
        in_biem_mau = bool(re.search(r'\b(form|forms|draft|drafts)\b', rel_path_lower)) or "biểu mẫu" in rel_path_lower
        is_policy_name = any(kw in relative_path for kw in ["Quy chế", "Quy trình", "Nội quy", "Sổ tay", "Hướng dẫn", "Regulations", "Procedure", "Manual", "Plan", "Chính sách"])
        
        is_template = False
        if is_policy_name and not in_biem_mau:
            if word_count < 150:
                is_template = True
        else:
            if in_biem_mau:
                if word_count < 200:
                    if total_placeholders > 1 or density > 0.02:
                        is_template = True
                else:
                    if density > 0.15:
                        is_template = True
            else:
                if word_count < 250:
                    if total_placeholders > 5 or density > 0.05:
                        is_template = True
                else:
                    if density > 0.25:
                        is_template = True

        if "họ và tên" in cleaned_lower and "ngày sinh" in cleaned_lower and word_count < 120 and (underscores > 1 or dots > 1):
            is_template = True

        if is_template:
            return "Empty Form Template", size, cleaned, header_orig_path, header_scan_target
        
        return "Real Content", size, cleaned, header_orig_path, header_scan_target

    def _detect_domain(self, filepath, rel_path, content_lower):
        rel_path_lower = rel_path.lower()
        if "07 - it" in rel_path_lower or "cict.qt.it" in rel_path_lower or "cict.cs.it" in rel_path_lower:
            return "IT (Công nghệ thông tin)"
        if "safety" in rel_path_lower or "hsse" in rel_path_lower or "ehs" in rel_path_lower or "pccc" in rel_path_lower or "cnch" in rel_path_lower or "bảo hộ lao động" in content_lower:
            return "HSSE (An toàn, Môi trường, An ninh)"
        if "kpi" in rel_path_lower or "okr" in rel_path_lower or "sskpi" in rel_path_lower or "kpi" in content_lower or "okr" in content_lower:
            return "KPI & OKR (Quản trị hiệu suất)"
        if "nạo vét" in rel_path_lower or "dredging" in rel_path_lower or "nạo vét duy tu" in content_lower:
            return "Dredging (Nạo vét bến cảng)"
        if "06 - hr" in rel_path_lower or "admin" in rel_path_lower or "nhân sự" in rel_path_lower or "hành chính" in rel_path_lower or "lao động" in content_lower or "hchr" in rel_path_lower:
            return "HR & Admin (Nhân sự & Hành chính)"
        if "09 - operation" in rel_path_lower or "ops" in rel_path_lower or "khai thác" in rel_path_lower or "xếp dỡ" in rel_path_lower or "sà lan" in content_lower or "cảng vụ" in content_lower:
            return "Operation (Khai thác cảng)"
        if "02 - finance" in rel_path_lower or "acc" in rel_path_lower or "kế toán" in rel_path_lower or "tài chính" in rel_path_lower or "chi tiêu" in rel_path_lower or "tạm ứng" in rel_path_lower:
            return "Finance & Accounting (Tài chính - Kế toán)"
        if "08 - marketing" in rel_path_lower or "mkt" in rel_path_lower or "marketing" in rel_path_lower or "khách hàng" in rel_path_lower or "truyền thông" in content_lower:
            return "Marketing & Sales (Tiếp thị & Chăm sóc khách hàng)"
            
        if "công nghệ thông tin" in content_lower or "phần mềm" in content_lower or "máy tính" in content_lower:
            return "IT (Công nghệ thông tin)"
        if "an toàn lao động" in content_lower or "phòng cháy" in content_lower or "môi trường" in content_lower:
            return "HSSE (An toàn, Môi trường, An ninh)"
        if "nạo vét" in content_lower or "độ sâu" in content_lower:
            return "Dredging (Nạo vét bến cảng)"
            
        return "Khác / Chung"

    def _detect_doc_type(self, filepath, rel_path, content_lower):
        filename_lower = os.path.basename(filepath).lower()
        if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quy chế", "quy chế chi tiêu", "chính sách", "policy", "regulations"]):
            return "Quy chế / Chính sách"
        if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quy trình", "hướng dẫn", "sổ tay", "procedure", "manual", "guide", "sổ tay kế toán", "sổ tay quản lý"]):
            return "Quy trình / Hướng dẫn"
        if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["quyết định", "biên bản", "nghị quyết", "minutes", "resolution", "decision"]):
            return "Quyết định / Biên bản"
        if any(kw in filename_lower or kw in content_lower[:1000] for kw in ["hợp đồng", "báo giá", "contract", "quotation"]):
            return "Hợp đồng / Báo giá"
        
        return "Tài liệu nghiệp vụ / Báo cáo"

    def _detect_language(self, content_lower):
        en_words = len(re.findall(r'\b(the|and|of|procedure|version|signed|date|page|cai lan|terminal)\b', content_lower))
        vn_chars = len(re.findall(r'[áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', content_lower))
        if en_words > 15 and vn_chars < 10:
            return "Tiếng Anh (EN)"
        elif vn_chars > 30 and en_words < 5:
            return "Tiếng Việt (VN)"
        elif en_words > 5 and vn_chars > 10:
            return "Song ngữ (EN/VN)"
        return "Tiếng Việt (VN)"

    def _detect_year(self, content_lower, filename, file_year=None):
        import datetime
        max_year = datetime.datetime.now().year + 1
        year_pattern = rf'\b(19\d{{2}}|20\d{{2}})\b'
        year_match = re.search(year_pattern, filename)
        if year_match:
            year = int(year_match.group(1))
            if 1900 <= year <= max_year:
                return year

        first_part = (content_lower or "")[:1000]
        years = [y for y in re.findall(year_pattern, first_part) if 1900 <= int(y) <= max_year]
        if not years:
            if isinstance(file_year, int) and 1900 <= file_year <= max_year:
                return file_year
            return "N/A"

        freq = {}
        for y in years:
            freq[y] = freq.get(y, 0) + 1
        sorted_years = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return int(sorted_years[0][0])

    def _source_signature(self, path, include_hash=False):
        try:
            stat = os.stat(path)
            signature = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
            if include_hash:
                digest = hashlib.sha256()
                with open(path, 'rb') as source_file:
                    for chunk in iter(lambda: source_file.read(1024 * 1024), b''):
                        digest.update(chunk)
                signature["sha256"] = digest.hexdigest()
            return signature
        except (OSError, ValueError):
            return None

    def _read_markdown_header(self, path):
        metadata = {}
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(2000)
            for key in ("ORIGINAL_PATH", "SCAN_TARGET", "SOURCE_SIZE", "SOURCE_MTIME_NS", "SOURCE_SHA256"):
                match = re.search(rf'<!--\s*{key}:\s*(.*?)\s*-->', head)
                if match:
                    metadata[key] = match.group(1).strip()
        except (OSError, UnicodeError):
            return {}
        return metadata

    def _markdown_needs_refresh(self, markdown_path, source_path, scan_target=None):
        if not os.path.exists(markdown_path):
            return True
        metadata = self._read_markdown_header(markdown_path)
        source = self._source_signature(source_path)
        if not source:
            return True
        expected_source = os.path.normcase(os.path.normpath(os.path.abspath(source_path)))
        stored_source = metadata.get("ORIGINAL_PATH", "")
        if not stored_source or os.path.normcase(os.path.normpath(os.path.abspath(stored_source))) != expected_source:
            return True
        try:
            if int(metadata.get("SOURCE_SIZE", "-1")) != source["size"] or int(metadata.get("SOURCE_MTIME_NS", "-1")) != source["mtime_ns"]:
                return True
            if scan_target and metadata.get("SCAN_TARGET", "") and os.path.normcase(os.path.normpath(os.path.abspath(metadata["SCAN_TARGET"]))) != os.path.normcase(os.path.normpath(os.path.abspath(scan_target))):
                return True
            stored_hash = metadata.get("SOURCE_SHA256", "")
            if not stored_hash:
                return True
            return self._source_signature(source_path, include_hash=True).get("sha256") != stored_hash
        except (TypeError, ValueError):
            return True

    def _write_markdown(self, path, content, source_path, scan_target):
        source = self._source_signature(source_path, include_hash=True) or {"size": 0, "mtime_ns": 0, "sha256": ""}
        body = content or ""
        body = re.sub(r'^<!--\s*(?:ORIGINAL_PATH|SCAN_TARGET|SOURCE_SIZE|SOURCE_MTIME_NS|SOURCE_SHA256):.*?-->\s*\n?', '', body, flags=re.MULTILINE)
        header = (
            f"<!-- ORIGINAL_PATH: {os.path.abspath(source_path)} -->\n"
            f"<!-- SCAN_TARGET: {os.path.abspath(scan_target)} -->\n"
            f"<!-- SOURCE_SIZE: {source['size']} -->\n"
            f"<!-- SOURCE_MTIME_NS: {source['mtime_ns']} -->\n"
            f"<!-- SOURCE_SHA256: {source.get('sha256', '')} -->\n\n"
        )
        temp_path = f"{path}.tmp-{os.getpid()}-{threading.get_ident()}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(header + body)
        os.replace(temp_path, path)

    @staticmethod
    def _source_size_limit(extension):
        if extension in IMAGE_EXTENSIONS:
            return IMAGE_SOURCE_LIMIT_BYTES
        if extension == ".zip":
            return ZIP_SOURCE_LIMIT_BYTES
        return DEFAULT_SOURCE_LIMIT_BYTES

    @staticmethod
    def _conversion_error_code(error):
        if isinstance(error, ConversionPolicyError):
            return error.code
        if isinstance(error, MissingDependencyException):
            return "missing_dependency"
        if isinstance(error, UnsupportedFormatException):
            return "unsupported"
        return "conversion_failed"

    @staticmethod
    def _error_summary(errors):
        summary = {}
        for item in errors:
            code = item.get("code", "conversion_failed")
            summary[code] = summary.get(code, 0) + 1
        return summary

    def scan_and_index(self):
        try:
            md_converter = MarkItDown()
            md_converter.register_converter(
                LocalOcrPdfConverter(self),
                priority=-1.0
            )
            md_converter.register_converter(
                LocalOcrImageConverter(self),
                priority=-1.0
            )
            md_converter.register_converter(
                LocalDocConverter(self),
                priority=-1.0
            )
            md_converter.register_converter(
                LocalXlsConverter(self),
                priority=-1.0
            )
        except Exception as e:
            import traceback
            log_dir = os.path.join(self.runtime_dir, "logs")
            try:
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "crash_log.txt")
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"sys.path: {sys.path}\n\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass
            return {"success": False, "error": f"Lỗi khởi tạo bộ chuyển đổi tài liệu: {str(e)}"}

        new_files_count = 0
        scan_errors = []
        supported_extensions = SUPPORTED_EXTENSIONS

        # Xác định thư mục quét mục tiêu
        scan_target = self.scan_dir if self.scan_dir else self.base_dir
        if not os.path.isdir(scan_target):
            return {"success": False, "error": f"Thư mục quét không tồn tại hoặc không phải thư mục: {scan_target}"}

        # Thư mục chỉ mục runtime; tuyệt đối không ghi ngược vào thư mục nguồn.
        app_markdown_root = self.runtime_markdown_root
        os.makedirs(app_markdown_root, exist_ok=True)

        # Dùng ID băm ổn định thay basename để tránh đè chỉ mục khi hai thư mục
        # khác nhau nhưng có cùng tên.
        scan_id = self._scan_id(scan_target)
        dest_folder_md_root = os.path.join(app_markdown_root, scan_id)
        os.makedirs(dest_folder_md_root, exist_ok=True)
        staging_root = os.path.join(self.runtime_dir, f".staging-{scan_id}-{os.getpid()}")
        if os.path.exists(staging_root):
            shutil.rmtree(staging_root, ignore_errors=True)
        os.makedirs(staging_root, exist_ok=True)

        expected_markdown_files = set()
        tasks = []
        managed_dirs = self._managed_source_dirs(scan_target)

        # Quét thư mục nguồn (chỉ đọc, KHÔNG ghi bất kỳ file nào vào scan_target)
        for root, dirs, files in os.walk(scan_target):
            dirs[:] = [
                directory for directory in dirs
                if not self._should_skip_source_dir(scan_target, os.path.join(root, directory), managed_dirs)
            ]
            for file in files:
                if file.startswith('~$'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    
                    rel_dir = os.path.relpath(root, scan_target)
                    if rel_dir == '.':
                        rel_dir = ''
                    
                    dest_markdown_dir = os.path.join(dest_folder_md_root, rel_dir)
                    os.makedirs(dest_markdown_dir, exist_ok=True)
                    new_markdown_path = self._cache_path(dest_markdown_dir, file_path)
                    
                    expected_markdown_files.add(os.path.normpath(new_markdown_path))

                    try:
                        source_size = os.path.getsize(file_path)
                    except OSError as error:
                        scan_errors.append({
                            "file": file_path,
                            "code": "source_unreadable",
                            "error": str(error),
                        })
                        continue
                    if source_size > self._source_size_limit(ext):
                        scan_errors.append({
                            "file": file_path,
                            "code": "too_large",
                            "error": "Tệp vượt giới hạn kích thước an toàn.",
                        })
                        continue
                    
                    is_stale = self._markdown_needs_refresh(new_markdown_path, file_path, scan_target)
                    if is_stale:
                        stage_md_path = os.path.join(
                            staging_root,
                            os.path.relpath(new_markdown_path, dest_folder_md_root),
                        )
                        tasks.append({
                            'src_path': file_path,
                            'dest_md_path': new_markdown_path,
                            'stage_md_path': stage_md_path,
                            'scan_target': scan_target
                        })

        # Thực thi xử lý đa luồng với kiểm soát tài nguyên
        total_tasks = len(tasks)
        completed_tasks = 0

        # Reset các cờ kiểm soát quét
        self._scan_paused = False
        self._scan_aborted = False
        self._pause_event.set()

        def run_single_task(task):
            nonlocal completed_tasks, new_files_count
            if self._scan_aborted:
                return

            self._pause_event.wait()

            if self._scan_aborted:
                return

            src_path = task['src_path']
            dest_md_path = task['dest_md_path']
            stage_md_path = task['stage_md_path']
            task_scan_target = task['scan_target']
            
            filename = os.path.basename(src_path)
            task_id = os.path.normcase(os.path.normpath(os.path.abspath(src_path)))
            
            with self.lock:
                self.active_files.append({"id": task_id, "filename": filename, "status": "Pending"})
                active_list = self.active_files[:4]
                percent = int((completed_tasks / total_tasks) * 100)
                self._report_progress(percent, active_list)
                
            success = False
            try:
                # Cập nhật trạng thái thành Working ngay trước khi chạy chuyển đổi
                with self.lock:
                    for item in self.active_files:
                        if item["id"] == task_id:
                            item["status"] = "Working"
                            break
                    percent = int((completed_tasks / total_tasks) * 100)
                    self._report_progress(percent, self.active_files[:4])

                # convert file
                if os.path.splitext(src_path)[1].lower() == ".zip":
                    with open(src_path, "rb") as archive_stream:
                        result = SafeZipConverter(md_converter).convert(
                            archive_stream,
                            StreamInfo(
                                extension=".zip",
                                filename=os.path.basename(src_path),
                                local_path=src_path,
                            ),
                        )
                else:
                    result = md_converter.convert_local(src_path)
                
                if self._scan_aborted:
                    with self.lock:
                        self.active_files = [f for f in self.active_files if f["id"] != task_id]
                        completed_tasks += 1
                        percent = int((completed_tasks / total_tasks) * 100)
                        self._report_progress(percent, self.active_files[:4])
                    return

                converted_text = (result.text_content or "").strip()
                if converted_text.lower().startswith("error during local"):
                    raise RuntimeError(converted_text)
                if not converted_text:
                    raise ConversionPolicyError("conversion_failed", "Bộ chuyển đổi không tạo được nội dung.")
                self._write_markdown(stage_md_path, converted_text, src_path, task_scan_target)
                success = True
            except Exception as e:
                print(f"Error converting task {src_path}: {e}")
                with self.lock:
                    scan_errors.append({
                        "file": src_path,
                        "code": self._conversion_error_code(e),
                        "error": str(e)
                    })
                if os.path.exists(stage_md_path):
                    try:
                        os.remove(stage_md_path)
                    except Exception:
                        pass
                
            if self._scan_aborted:
                if os.path.exists(stage_md_path):
                    try:
                        os.remove(stage_md_path)
                    except Exception:
                        pass
                with self.lock:
                    self.active_files = [f for f in self.active_files if f["id"] != task_id]
                    completed_tasks += 1
                    percent = int((completed_tasks / total_tasks) * 100)
                    self._report_progress(percent, self.active_files[:4])
                return

            with self.lock:
                self.active_files = [f for f in self.active_files if f["id"] != task_id]
                if success:
                    new_files_count += 1
                completed_tasks += 1
                percent = int((completed_tasks / total_tasks) * 100)
                active_list = self.active_files[:4]
                self._report_progress(percent, active_list)

        if total_tasks > 0:
            workers = self.get_safe_workers_count()
            self.executor = ThreadPoolExecutor(max_workers=workers)
            try:
                # Chạy đa luồng bằng executor.map
                self.executor.map(run_single_task, tasks)
            finally:
                if self.executor:
                    # Nếu bị abort, không chờ các luồng phụ đang chạy kết thúc
                    wait_threads = not self._scan_aborted
                    self.executor.shutdown(wait=wait_threads)
                    self.executor = None

        # Kiểm tra xem có bị abort trong lúc quét không
        if self._scan_aborted:
            shutil.rmtree(staging_root, ignore_errors=True)
            self._report_progress(0, [])
            return {"success": False, "error": "Đã hủy quét tài liệu"}

        # Publish converted files only after every task completed successfully.
        for task in tasks:
            stage_path = task['stage_md_path']
            if os.path.exists(stage_path):
                os.makedirs(os.path.dirname(task['dest_md_path']), exist_ok=True)
                os.replace(stage_path, task['dest_md_path'])
        shutil.rmtree(staging_root, ignore_errors=True)

        # Ghi nhận file mồ côi; chỉ xóa sau khi index mới commit thành công.
        orphaned_markdown_files = []
        for root, dirs, files in os.walk(dest_folder_md_root):
            for file in files:
                if file.lower().endswith('.md'):
                    md_path = os.path.normpath(os.path.join(root, file))
                    if md_path not in expected_markdown_files:
                        orphaned_markdown_files.append(md_path)

        # Đảm bảo báo cáo tiến trình 100% khi kết thúc
        self._report_progress(100, [])

        # 2. Quét TOÀN BỘ thư mục MARKDOWN tập trung để tạo search_db.js hợp nhất
        db_entries = []
        for root, dirs, files in os.walk(app_markdown_root):
            for file in files:
                if file.startswith('~$'):
                    continue
                if file.lower().endswith('.md'):
                    filepath = os.path.join(root, file)
                    normalized_filepath = os.path.normcase(os.path.normpath(filepath))
                    if normalized_filepath.startswith(os.path.normcase(os.path.normpath(dest_folder_md_root)) + os.sep) and normalized_filepath not in {
                        os.path.normcase(path) for path in expected_markdown_files
                    }:
                        continue
                    try:
                        rel_path = os.path.relpath(filepath, self.base_dir).replace('\\', '/')
                    except ValueError:
                        rel_path = os.path.abspath(filepath).replace('\\', '/')
                    
                    if file.lower() in ['readme.md', 'changelog.md', 'markitdown guide.md', 'idea.html.md']:
                        continue

                    rel_root = os.path.relpath(root, app_markdown_root)
                    entry_scan_id = rel_root.split(os.sep, 1)[0] if rel_root != '.' else scan_id
                        
                    category, size, cleaned_content, header_orig_path, header_scan_target = self._classify_file(filepath, rel_path)
                    if category == "Real Content":
                        cleaned_lower = cleaned_content.lower()
                        domain = self._detect_domain(filepath, rel_path, cleaned_lower)
                        doc_type = self._detect_doc_type(filepath, rel_path, cleaned_lower)
                        language = self._detect_language(cleaned_lower)
                        original_filename = os.path.basename(header_orig_path) if header_orig_path else file[:-3]
                        
                        # Xác định đường dẫn gốc và đường dẫn tuyệt đối
                        if header_orig_path:
                            absolute_original_path = os.path.normpath(header_orig_path)
                            if header_scan_target:
                                try:
                                    original_rel_path = os.path.relpath(header_orig_path, header_scan_target).replace('\\', '/')
                                except ValueError:
                                    original_rel_path = os.path.basename(header_orig_path)
                            else:
                                original_rel_path = os.path.basename(header_orig_path)
                        else:
                            rel_markdown_subdir = os.path.relpath(root, app_markdown_root)
                            if rel_markdown_subdir == '.':
                                rel_markdown_subdir = ''
                            original_rel_path = os.path.join(rel_markdown_subdir, original_filename).replace('\\', '/')
                            
                            # Fallback candidate paths
                            cand_base = os.path.normpath(os.path.join(self.base_dir, original_rel_path))
                            cand_scan = os.path.normpath(os.path.join(scan_target, original_filename))
                            if os.path.exists(cand_base):
                                absolute_original_path = cand_base
                            elif os.path.exists(cand_scan):
                                absolute_original_path = cand_scan
                            else:
                                absolute_original_path = cand_base
                        
                        file_year = 0
                        file_month = 0
                        try:
                            if os.path.exists(absolute_original_path):
                                import datetime
                                mtime = os.path.getmtime(absolute_original_path)
                                dt = datetime.datetime.fromtimestamp(mtime)
                                file_year = dt.year
                                file_month = dt.month
                        except Exception:
                            pass

                        title_clean = remove_diacritics(original_filename)
                        content_clean = remove_diacritics(cleaned_content)
                        word_count = len(cleaned_content.split()) if cleaned_content else 1
                        year = self._detect_year(cleaned_lower, original_filename, file_year)
                        ocr_quality_score = self._calculate_ocr_quality_score(cleaned_content)
                        source_type = self._classify_source(original_filename, rel_path, cleaned_content, ocr_quality_score)
                        source_signature = self._source_signature(absolute_original_path)
                        source_metadata = self._read_markdown_header(filepath)

                        db_entries.append({
                            "scan_id": entry_scan_id,
                            "title": original_filename,
                            "title_clean": title_clean,
                            "path": rel_path,
                            "original_path": original_rel_path,
                            "absolute_original_path": absolute_original_path,
                            "domain": domain,
                            "doc_type": doc_type,
                            "language": language,
                            "year": year,
                            "file_year": file_year,
                            "file_month": file_month,
                            "source_type": source_type,
                            "ocr_quality_score": ocr_quality_score,
                            "wordCount": word_count,
                            "content": cleaned_content,
                            "content_clean": content_clean,
                            "source_size": source_signature.get("size") if source_signature else None,
                            "source_mtime_ns": source_signature.get("mtime_ns") if source_signature else None,
                            "source_sha256": source_metadata.get("SOURCE_SHA256") or None
                        })

        # Chỉ loại bản ghi trùng cùng source identity; tài liệu giống nội dung
        # nhưng đến từ các nguồn khác nhau vẫn phải giữ nguyên.
        try:
            deduped_entries = []
            seen_keys = {}

            def entry_quality(entry):
                quality = float(entry.get("ocr_quality_score") or 0)
                words = int(entry.get("wordCount") or 0)
                file_year = int(entry.get("file_year") or 0)
                return (quality, words, file_year)

            for entry in db_entries:
                original_key = os.path.normcase(os.path.normpath(os.path.abspath(entry.get("absolute_original_path", ""))))
                key = f"{entry.get('scan_id') or 'legacy'}:{original_key or entry.get('original_path') or entry.get('path')}"
                if key in seen_keys:
                    existing_idx = seen_keys[key]
                    if entry_quality(entry) > entry_quality(deduped_entries[existing_idx]):
                        deduped_entries[existing_idx] = entry
                    continue
                seen_keys[key] = len(deduped_entries)
                deduped_entries.append(entry)

            db_entries = deduped_entries
        except Exception as e:
            print(f"Error de-duplicating search db: {e}")

        current_scan_entries = sum(1 for entry in db_entries if entry.get("scan_id") == scan_id)
        if expected_markdown_files and current_scan_entries == 0:
            return {
                "success": False,
                "error": "Đã tạo Markdown nhưng không tạo được tài liệu tìm kiếm; index cũ được giữ nguyên.",
                "new_files": new_files_count,
                "total_entries": self.index_store.count_documents(),
                "errors": scan_errors[:50],
                "error_count": len(scan_errors),
                "error_summary": self._error_summary(scan_errors),
            }

        # Prepare all filesystem outputs before committing SQLite.
        output_js = self.runtime_search_db
        output_tmp = f"{output_js}.tmp-{os.getpid()}"
        status_tmp = f"{self.runtime_status_file}.tmp-{os.getpid()}"
        try:
            db_json = json.dumps(db_entries, ensure_ascii=False, indent=2)
            with open(output_tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(f"var SEARCH_DB = {db_json};\n")

            scanned_dict = {}
            if os.path.exists(self.runtime_status_file):
                with open(self.runtime_status_file, 'r', encoding='utf-8') as f:
                    try:
                        scanned_dict = json.loads(f.read().strip() or '{}')
                    except (TypeError, ValueError):
                        scanned_dict = {}
            normalized_path = os.path.normcase(os.path.normpath(os.path.abspath(scan_target)))
            scanned_dict[normalized_path] = sum(1 for entry in db_entries if entry.get("scan_id") == scan_id)
            with open(status_tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps(scanned_dict, ensure_ascii=False, indent=2))
        except Exception as e:
            for temp_path in (output_tmp, status_tmp):
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass
            return {"success": False, "error": f"Không thể chuẩn bị index runtime: {e}"}

        try:
            self.index_store.replace_entries(db_entries)
            os.replace(output_tmp, output_js)
            os.replace(status_tmp, self.runtime_status_file)
        except Exception as e:
            for temp_path in (output_tmp, status_tmp):
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
                    pass
            scan_errors.append({
                "file": self.runtime_index_db,
                "code": "index_commit_failed",
                "error": f"SQLite/runtime commit failed: {e}",
            })
            print(f"Error committing runtime index: {e}")
            return {
                "success": False,
                "new_files": 0,
                "total_entries": 0,
                "errors": scan_errors[:50],
                "error_count": len(scan_errors),
                "error_summary": self._error_summary(scan_errors),
            }

        for md_path in orphaned_markdown_files:
            try:
                if os.path.exists(md_path):
                    os.remove(md_path)
            except OSError as e:
                print(f"Error removing orphaned md file {md_path}: {e}")
        for root, dirs, files in os.walk(dest_folder_md_root, topdown=False):
            if root != dest_folder_md_root:
                try:
                    if not os.listdir(root):
                        os.rmdir(root)
                except OSError:
                    pass

        return {
            "success": True,
            "new_files": new_files_count,
            "total_entries": len(db_entries),
            "errors": scan_errors[:50],
            "error_count": len(scan_errors),
            "error_summary": self._error_summary(scan_errors),
        }

def main():
    # Xác định thư mục gốc chính xác
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    api = Api(base_dir)
    
    # Keep the UI outside the executable so HTML changes do not require a rebuild.
    resource_roots = [base_dir, os.path.dirname(base_dir)]
    if getattr(sys, '_MEIPASS', None):
        resource_roots.append(sys._MEIPASS)
    html_path = next(
        (
            os.path.join(root, 'data', 'SuperSearch.html')
            for root in resource_roots
            if os.path.isfile(os.path.join(root, 'data', 'SuperSearch.html'))
        ),
        os.path.join(base_dir, 'data', 'SuperSearch.html'),
    )
    
    # Chuyển đổi thành URL file:// để tránh sử dụng Bottle local server (tránh lỗi 404)
    file_url = 'file:///' + os.path.abspath(html_path).replace('\\', '/')

    width = 960
    height = 540
    
    # Tính toán tọa độ x, y để căn giữa màn hình
    try:
        screens = webview.screens
        if screens:
            primary = screens[0]
            x = (primary.width - width) // 2
            y = (primary.height - height) // 2
        else:
            x = None
            y = None
    except Exception:
        x = None
        y = None

    window = webview.create_window(
        title='SuperSearch - Tra cứu tài liệu siêu tốc',
        url=file_url,
        js_api=api,
        width=width,
        height=height,
        min_size=(width, height),
        x=x,
        y=y,
        resizable=True
    )
    api.set_window(window)
    webview.start()

if __name__ == '__main__':
    main()
