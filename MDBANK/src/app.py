import os
import sys

# Thêm đường dẫn Lib vào sys.path để nạp thư viện ngoài cục bộ
if getattr(sys, 'frozen', False):
    lib_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'src', 'Lib')
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
import pytesseract
import pdfplumber
from PIL import Image
import olefile
import xlrd
from markitdown import MarkItDown, DocumentConverter, DocumentConverterResult
import unicodedata

def remove_diacritics(text):
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    no_marks = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    cleaned = no_marks.replace('đ', 'd').replace('Đ', 'D')
    return cleaned.lower()

class LocalOcrPdfConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.base_dir = api.base_dir
        self.base_dir_meipass = api.base_dir_meipass
        self.base_dir_exe = api.api.base_dir_exe if hasattr(api, 'api') and hasattr(api.api, 'base_dir_exe') else api.base_dir_exe

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext == '.pdf'

    def convert(self, file_stream, stream_info, **kwargs):
        if getattr(sys, 'frozen', False):
            tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tesseract.exe')
            tesseract_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tesseract.exe')
            tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tessdata')
            tessdata_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tessdata')
        else:
            tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tesseract.exe')
            tesseract_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tesseract.exe')
            tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tessdata')
            tessdata_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tessdata')

        tesseract_global = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

        if os.path.exists(tesseract_local_meipass):
            pytesseract.pytesseract.tesseract_cmd = tesseract_local_meipass
            os.environ['TESSDATA_PREFIX'] = tessdata_local_meipass
        elif os.path.exists(tesseract_local_exe):
            pytesseract.pytesseract.tesseract_cmd = tesseract_local_exe
            os.environ['TESSDATA_PREFIX'] = tessdata_local_exe
        else:
            pytesseract.pytesseract.tesseract_cmd = tesseract_global
            tessdata_global = os.path.abspath(os.path.join(self.base_dir, '..', 'CONVERSION_LOGS', 'tessdata'))
            if os.path.exists(tessdata_global):
                os.environ['TESSDATA_PREFIX'] = tessdata_global

        pdf_target = None
        if stream_info and stream_info.local_path and os.path.exists(stream_info.local_path):
            pdf_target = stream_info.local_path

        text_content = []
        try:
            if pdf_target:
                with pdfplumber.open(pdf_target) as pdf:
                    for page in pdf.pages:
                        if self.api._scan_aborted:
                            break
                        if self.api._scan_paused:
                            self.api._pause_event.wait()
                            if self.api._scan_aborted:
                                break
                        text = page.extract_text()
                        if text:
                            text_content.append(text)
            else:
                file_stream.seek(0)
                pdf_bytes = io.BytesIO(file_stream.read())
                with pdfplumber.open(pdf_bytes) as pdf:
                    for page in pdf.pages:
                        if self.api._scan_aborted:
                            break
                        if self.api._scan_paused:
                            self.api._pause_event.wait()
                            if self.api._scan_aborted:
                                break
                        text = page.extract_text()
                        if text:
                            text_content.append(text)
        except Exception:
            pass
            
        full_text = "\n\n".join(text_content).strip()
        
        if not full_text or len(full_text) < 100:
            ocr_pages = []
            try:
                if pdf_target:
                    with pdfplumber.open(pdf_target) as pdf:
                        for page_num, page in enumerate(pdf.pages, 1):
                            if self.api._scan_aborted:
                                break
                            if self.api._scan_paused:
                                self.api._pause_event.wait()
                                if self.api._scan_aborted:
                                    break
                            with self.api.ocr_lock:
                                page_img = page.to_image(resolution=150)
                                img_bytes = io.BytesIO()
                                page_img.original.save(img_bytes, format='PNG')
                                img_bytes.seek(0)
                                
                                text = pytesseract.image_to_string(
                                    Image.open(img_bytes),
                                    lang='vie+eng'
                                )
                            ocr_pages.append(f"<!-- PAGE {page_num} (OCR Mode) -->\n\n{text}")
                else:
                    file_stream.seek(0)
                    pdf_bytes = io.BytesIO(file_stream.read())
                    with pdfplumber.open(pdf_bytes) as pdf:
                        for page_num, page in enumerate(pdf.pages, 1):
                            if self.api._scan_aborted:
                                break
                            if self.api._scan_paused:
                                self.api._pause_event.wait()
                                if self.api._scan_aborted:
                                    break
                            with self.api.ocr_lock:
                                page_img = page.to_image(resolution=150)
                                img_bytes = io.BytesIO()
                                page_img.original.save(img_bytes, format='PNG')
                                img_bytes.seek(0)
                                
                                text = pytesseract.image_to_string(
                                    Image.open(img_bytes),
                                    lang='vie+eng'
                                )
                            ocr_pages.append(f"<!-- PAGE {page_num} (OCR Mode) -->\n\n{text}")
                full_text = "\n\n".join(ocr_pages).strip()
            except Exception as e:
                full_text = f"Error during local OCR: {str(e)}"
                
        return DocumentConverterResult(markdown=full_text)

class LocalOcrImageConverter(DocumentConverter):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.base_dir = api.base_dir
        self.base_dir_meipass = api.base_dir_meipass
        self.base_dir_exe = api.api.base_dir_exe if hasattr(api, 'api') and hasattr(api.api, 'base_dir_exe') else api.base_dir_exe

    def accepts(self, file_stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        return ext in ['.png', '.jpg', '.jpeg']

    def convert(self, file_stream, stream_info, **kwargs):
        if getattr(sys, 'frozen', False):
            tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tesseract.exe')
            tesseract_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tesseract.exe')
            tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'src', 'Tesseract-OCR', 'tessdata')
            tessdata_local_exe = os.path.join(self.base_dir_exe, 'src', 'Tesseract-OCR', 'tessdata')
        else:
            tesseract_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tesseract.exe')
            tesseract_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tesseract.exe')
            tessdata_local_meipass = os.path.join(self.base_dir_meipass, 'Tesseract-OCR', 'tessdata')
            tessdata_local_exe = os.path.join(self.base_dir_exe, 'Tesseract-OCR', 'tessdata')

        tesseract_global = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

        if os.path.exists(tesseract_local_meipass):
            pytesseract.pytesseract.tesseract_cmd = tesseract_local_meipass
            os.environ['TESSDATA_PREFIX'] = tessdata_local_meipass
        elif os.path.exists(tesseract_local_exe):
            pytesseract.pytesseract.tesseract_cmd = tesseract_local_exe
            os.environ['TESSDATA_PREFIX'] = tessdata_local_exe
        else:
            pytesseract.pytesseract.tesseract_cmd = tesseract_global
            tessdata_global = os.path.abspath(os.path.join(self.base_dir, '..', 'CONVERSION_LOGS', 'tessdata'))
            if os.path.exists(tessdata_global):
                os.environ['TESSDATA_PREFIX'] = tessdata_global

        file_stream.seek(0)
        try:
            with self.api.ocr_lock:
                img = Image.open(file_stream)
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

    def load_saved_folder(self):
        try:
            db_dir = os.path.join(self.base_dir, 'data')
            folder_path_file = os.path.join(db_dir, 'folder_path.txt')
            if os.path.exists(folder_path_file):
                with open(folder_path_file, 'r', encoding='utf-8') as f:
                    path = f.read().strip()
                    if path and os.path.exists(path):
                        self.scan_dir = os.path.normpath(path)
                        self._restore_db_for_folder(self.scan_dir)
                        return
            self._restore_db_for_folder(self.base_dir)
        except Exception as e:
            print(f"Error loading scan_dir: {e}")

    def save_saved_folder(self, path):
        try:
            db_dir = os.path.join(self.base_dir, 'data')
            os.makedirs(db_dir, exist_ok=True)
            folder_path_file = os.path.join(db_dir, 'folder_path.txt')
            with open(folder_path_file, 'w', encoding='utf-8') as f:
                f.write(path.strip())
            self.scan_dir = os.path.normpath(path)
            self._restore_db_for_folder(self.scan_dir)
        except Exception as e:
            print(f"Error saving scan_dir: {e}")

    def _get_db_filename(self, folder_path):
        import hashlib
        normalized = os.path.normpath(folder_path).lower()
        path_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        return f"search_db_{path_hash}.js"

    def _restore_db_for_folder(self, folder_path):
        try:
            db_dir = os.path.join(self.base_dir, 'data')
            db_filename = self._get_db_filename(folder_path)
            src_db_file = os.path.join(db_dir, db_filename)
            dest_db_file = os.path.join(db_dir, 'search_db.js')
            
            if os.path.exists(src_db_file):
                shutil.copy2(src_db_file, dest_db_file)
                return True
            else:
                os.makedirs(db_dir, exist_ok=True)
                with open(dest_db_file, 'w', encoding='utf-8') as f:
                    f.write("var SEARCH_DB = [];\n")
                return False
        except Exception as e:
            print(f"Error restoring db: {e}")
            return False

    def check_folder_status(self, folder_path=None):
        try:
            if not folder_path:
                folder_path = self.scan_dir if self.scan_dir else self.base_dir
            normalized_path = os.path.normpath(folder_path)
            
            ss_folder_file = os.path.join(self.base_dir, 'data', 'SSFolder.txt')
            if os.path.exists(ss_folder_file):
                with open(ss_folder_file, 'r', encoding='utf-8') as f:
                    try:
                        scanned_dict = json.loads(f.read().strip())
                        if normalized_path in scanned_dict:
                            return {
                                "scanned": True,
                                "total_entries": scanned_dict[normalized_path]
                            }
                    except Exception:
                        pass
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
                self.save_saved_folder(selected_dir)
                status = self.check_folder_status(selected_dir)
                return {
                    "success": True,
                    "folder_path": selected_dir,
                    "scanned": status.get("scanned", False),
                    "total_entries": status.get("total_entries", 0)
                }
        return {"success": False, "error": "Đã hủy chọn thư mục"}

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
        if os.path.exists(path):
            # Mở Windows Explorer và chọn file
            subprocess.run(f'explorer.exe /select,"{path}"')
            return True
        else:
            # Nếu file không tồn tại, thử mở thư mục cha
            parent = os.path.dirname(path)
            if os.path.exists(parent):
                subprocess.run(f'explorer.exe "{parent}"')
                return True
        return False

    def _clean_content(self, content):
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
        tokens = re.findall(r'[A-Za-zÀ-ỹĐđ0-9]{2,}', text or "")
        if not tokens:
            return 0.0
        valid_tokens = 0
        for token in tokens:
            letters = len(re.findall(r'[A-Za-zÀ-ỹĐđ0-9]', token))
            if letters / max(1, len(token)) >= 0.75:
                valid_tokens += 1
        symbol_count = len(re.findall(r'[^A-Za-zÀ-ỹĐđ0-9\s.,;:!?()/\\\-\[\]_%]', text or ""))
        symbol_penalty = min(0.35, symbol_count / max(1, len(text or "")))
        score = (valid_tokens / len(tokens)) - symbol_penalty
        return round(max(0.0, min(1.0, score)), 3)

    def _classify_source(self, filepath, rel_path, content, ocr_quality_score):
        ext = self._infer_original_ext(filepath)
        content_lower = (content or "").lower()
        rel_lower = (rel_path or "").lower()

        if ocr_quality_score < 0.35:
            return "low_confidence_ocr"

        if ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.doc', '.xls', '.md']:
            return "formal_document"

        if ext in ['.png', '.jpg', '.jpeg']:
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
            return "Unknown", 0, ""

        if size == 0:
            return "Empty/Near Empty", size, ""

        content = ""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            try:
                with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return "Error Reading", size, ""

        stripped_content = content.strip()
        if not stripped_content:
            return "Empty/Near Empty", size, ""

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

        ext = self._infer_original_ext(relative_path)
        is_image_ocr = ext in ['.png', '.jpg', '.jpeg']
        words = re.findall(r'\w+', cleaned)
        word_count = len(words)

        if is_image_ocr:
            if len(cleaned) < 20 or word_count < 3 or is_generic_cover:
                return "Empty/Near Empty", size, cleaned
        elif len(cleaned) < 50 or is_generic_cover:
            return "Empty/Near Empty", size, cleaned

        if self._is_ocr_noise(cleaned):
            return "Empty/Near Empty", size, cleaned

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
            return "Empty Form Template", size, cleaned
        
        if "Error during local OCR:" in cleaned:
            return "Error Reading", size, cleaned
        
        return "Real Content", size, cleaned

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
        year_match = re.search(r'\b(201\d|202\d)\b', filename)
        if year_match:
            return int(year_match.group(1))

        first_part = (content_lower or "")[:1000]
        years = re.findall(r'\b(201\d|202\d)\b', first_part)
        if not years:
            if isinstance(file_year, int) and 2010 <= file_year <= 2029:
                return file_year
            return "N/A"

        freq = {}
        for y in years:
            freq[y] = freq.get(y, 0) + 1
        sorted_years = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return int(sorted_years[0][0])

    def _restore_original_files(self, scan_target):
        orig_dir = os.path.join(scan_target, 'ORIGINAL')
        if not os.path.exists(orig_dir):
            return
        for root, dirs, files in os.walk(orig_dir, topdown=False):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, orig_dir)
                dest_file = os.path.join(scan_target, rel_path)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                try:
                    if os.path.exists(dest_file):
                        os.remove(src_file)
                    else:
                        shutil.move(src_file, dest_file)
                except Exception as e:
                    print(f"Error restoring file {src_file}: {e}")
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except Exception:
                    pass
        try:
            if os.path.exists(orig_dir) and not os.listdir(orig_dir):
                os.rmdir(orig_dir)
        except Exception as e:
            print(f"Error removing ORIGINAL dir: {e}")

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
            log_dir = os.path.join(self.base_dir_exe, "logs")
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
        supported_extensions = ['.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg', '.jpeg', '.doc', '.xls']

        # Xác định thư mục quét mục tiêu
        scan_target = self.scan_dir if self.scan_dir else self.base_dir
        if not os.path.exists(scan_target):
            return {"success": False, "error": f"Thư mục quét không tồn tại: {scan_target}"}

        # Khôi phục các file gốc cũ từ ORIGINAL nếu có
        self._restore_original_files(scan_target)

        # Tạo thư mục đích MARKDOWN ở chính thư mục quét
        markdown_root = os.path.join(scan_target, 'MARKDOWN')
        os.makedirs(markdown_root, exist_ok=True)

        expected_markdown_files = set()
        tasks = []

        # Quét thống nhất cho tất cả các thư mục quét (Không phân biệt mặc định/tùy chọn)
        for root, dirs, files in os.walk(scan_target):
            rel_parts = set(os.path.relpath(root, scan_target).lower().replace('\\', '/').split('/'))
            if rel_parts & {'__pycache__', 'build', 'dist', '.git', '.gemini', '.agents', 'markdown', 'original', 'src', 'docs', 'data', 'logs', 'build_temp', 'lib', 'scr', 'node_modules', '.vs', '.vscode'}:
                continue
            for file in files:
                if file.startswith('~$'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    
                    rel_dir = os.path.relpath(root, scan_target)
                    if rel_dir == '.':
                        rel_dir = ''
                    
                    dest_markdown_dir = os.path.join(markdown_root, rel_dir)
                    os.makedirs(dest_markdown_dir, exist_ok=True)
                    new_markdown_path = os.path.join(dest_markdown_dir, file + ".md")
                    
                    expected_markdown_files.add(os.path.normpath(new_markdown_path))
                    
                    is_corrupted = False
                    if os.path.exists(new_markdown_path):
                        try:
                            with open(new_markdown_path, 'r', encoding='utf-8', errors='ignore') as f_check:
                                head = f_check.read(200)
                                if "Error during local OCR:" in head:
                                    is_corrupted = True
                        except Exception:
                            pass

                    if not os.path.exists(new_markdown_path) or is_corrupted:
                        if is_corrupted:
                            try:
                                os.remove(new_markdown_path)
                            except Exception:
                                pass
                        tasks.append({
                            'src_path': file_path,
                            'dest_md_path': new_markdown_path,
                            'dest_orig_path': None,
                            'clean_src_after': False
                        })
                elif ext == '.md':
                    file_path = os.path.join(root, file)
                    
                    rel_dir = os.path.relpath(root, scan_target)
                    if rel_dir == '.':
                        rel_dir = ''
                    
                    dest_markdown_dir = os.path.join(markdown_root, rel_dir)
                    os.makedirs(dest_markdown_dir, exist_ok=True)
                    new_markdown_path = os.path.join(dest_markdown_dir, file)
                    
                    expected_markdown_files.add(os.path.normpath(new_markdown_path))
                    
                    if not os.path.exists(new_markdown_path):
                        try:
                            shutil.copy2(file_path, new_markdown_path)
                        except Exception as e:
                            print(f"Error copying md file {file_path}: {e}")

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
            dest_orig_path = task['dest_orig_path']
            clean_src_after = task['clean_src_after']
            
            filename = os.path.basename(src_path)
            
            with self.lock:
                self.active_files.append({"filename": filename, "status": "Pending"})
                active_list = self.active_files[:4]
                percent = int((completed_tasks / total_tasks) * 100)
                self._report_progress(percent, active_list)
                
            success = False
            try:
                # Cập nhật trạng thái thành Working ngay trước khi chạy chuyển đổi
                with self.lock:
                    for item in self.active_files:
                        if item["filename"] == filename:
                            item["status"] = "Working"
                            break
                    percent = int((completed_tasks / total_tasks) * 100)
                    self._report_progress(percent, self.active_files[:4])

                # convert file
                result = md_converter.convert(src_path)
                
                if self._scan_aborted:
                    with self.lock:
                        self.active_files = [f for f in self.active_files if f["filename"] != filename]
                    completed_tasks += 1
                    percent = int((completed_tasks / total_tasks) * 100)
                    self._report_progress(percent, self.active_files[:4])
                    return

                with open(dest_md_path, 'w', encoding='utf-8') as f:
                    f.write(result.text_content)
                success = True
            except Exception as e:
                print(f"Error converting task {src_path}: {e}")
                with self.lock:
                    scan_errors.append({
                        "file": src_path,
                        "error": str(e)
                    })
                if os.path.exists(dest_md_path):
                    try:
                        os.remove(dest_md_path)
                    except Exception:
                        pass
                
            if self._scan_aborted:
                if os.path.exists(dest_md_path):
                    try:
                        os.remove(dest_md_path)
                    except Exception:
                        pass
                with self.lock:
                    self.active_files = [f for f in self.active_files if f["filename"] != filename]
                    completed_tasks += 1
                    percent = int((completed_tasks / total_tasks) * 100)
                    self._report_progress(percent, self.active_files[:4])
                return

            if dest_orig_path:
                if not os.path.exists(dest_orig_path):
                    try:
                        shutil.move(src_path, dest_orig_path)
                    except Exception as e:
                        print(f"Error moving {src_path} to {dest_orig_path}: {e}")
                elif clean_src_after:
                    try:
                        os.remove(src_path)
                    except Exception as e:
                        print(f"Error removing redundant file {src_path}: {e}")
                        
            with self.lock:
                self.active_files = [f for f in self.active_files if f["filename"] != filename]
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
            self._report_progress(0, [])
            return {"success": False, "error": "Đã hủy quét tài liệu"}

        # Dọn dẹp các tệp .md mồ côi không nằm trong đợt quét này
        for root, dirs, files in os.walk(markdown_root):
            for file in files:
                if file.lower().endswith('.md'):
                    md_path = os.path.normpath(os.path.join(root, file))
                    if md_path not in expected_markdown_files:
                        try:
                            os.remove(md_path)
                        except Exception as e:
                            print(f"Error removing orphaned md file {md_path}: {e}")

        # Dọn dẹp các thư mục con rỗng trong MARKDOWN
        for root, dirs, files in os.walk(markdown_root, topdown=False):
            if root == markdown_root:
                continue
            try:
                if not os.listdir(root):
                    os.rmdir(root)
            except Exception:
                pass

        # Đảm bảo báo cáo tiến trình 100% khi kết thúc
        self._report_progress(100, [])

        # 2. Quét thư mục MARKDOWN để tạo search_db.js
        db_entries = []
        for root, dirs, files in os.walk(markdown_root):
            if any(p in root.lower() for p in ['__pycache__', 'build', 'dist', '.git', '.gemini', '.agents']):
                continue
            for file in files:
                if file.startswith('~$'):
                    continue
                if file.lower().endswith('.md'):
                    filepath = os.path.join(root, file)
                    try:
                        rel_path = os.path.relpath(filepath, self.base_dir).replace('\\', '/')
                    except ValueError:
                        rel_path = os.path.abspath(filepath).replace('\\', '/')
                    
                    if file.lower() in ['readme.md', 'changelog.md', 'markitdown guide.md', 'idea.html.md']:
                        continue
                        
                    category, size, cleaned_content = self._classify_file(filepath, rel_path)
                    if category == "Real Content":
                        cleaned_lower = cleaned_content.lower()
                        domain = self._detect_domain(filepath, rel_path, cleaned_lower)
                        doc_type = self._detect_doc_type(filepath, rel_path, cleaned_lower)
                        language = self._detect_language(cleaned_lower)
                        original_filename = file[:-3] if file.lower().endswith('.md') else file
                        
                        rel_markdown_subdir = os.path.relpath(root, markdown_root)
                        if rel_markdown_subdir == '.':
                            rel_markdown_subdir = ''
                            
                        # Đường dẫn gốc trỏ trực tiếp đến file trong scan_target
                        original_rel_path = os.path.join(rel_markdown_subdir, original_filename).replace('\\', '/')
                        absolute_original_path = os.path.abspath(os.path.join(scan_target, rel_markdown_subdir, original_filename))
                        
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

                        db_entries.append({
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
                            "content_clean": content_clean
                        })

        # Loại kết quả trùng trước khi ghi DB tìm kiếm.
        try:
            import hashlib
            deduped_entries = []
            seen_keys = {}

            def entry_quality(entry):
                quality = float(entry.get("ocr_quality_score") or 0)
                words = int(entry.get("wordCount") or 0)
                file_year = int(entry.get("file_year") or 0)
                return (quality, words, file_year)

            for entry in db_entries:
                original_key = os.path.normcase(os.path.normpath(entry.get("original_path", "")))
                content_key = hashlib.md5((entry.get("content_clean", "")[:2500]).encode('utf-8', errors='ignore')).hexdigest()
                title_key = remove_diacritics(entry.get("title", ""))
                key = original_key or f"{title_key}:{content_key}"
                soft_key = f"{title_key}:{content_key}"

                chosen_key = key
                if soft_key in seen_keys:
                    chosen_key = soft_key

                if chosen_key in seen_keys:
                    existing_idx = seen_keys[chosen_key]
                    if entry_quality(entry) > entry_quality(deduped_entries[existing_idx]):
                        deduped_entries[existing_idx] = entry
                    continue

                if soft_key not in seen_keys:
                    seen_keys[soft_key] = len(deduped_entries)
                seen_keys[chosen_key] = len(deduped_entries)
                deduped_entries.append(entry)

            db_entries = deduped_entries
        except Exception as e:
            print(f"Error de-duplicating search db: {e}")

        # Save search_db.js
        output_js = os.path.join(self.base_dir, 'data', 'search_db.js')
        try:
            os.makedirs(os.path.dirname(output_js), exist_ok=True)
        except Exception:
            pass
        db_json = json.dumps(db_entries, ensure_ascii=False, indent=2)
        with open(output_js, 'w', encoding='utf-8') as f:
            f.write(f"var SEARCH_DB = {db_json};\n")

        # Đồng thời lưu một bản sao phụ cho folder này
        try:
            db_filename = self._get_db_filename(scan_target)
            backup_js = os.path.join(self.base_dir, 'data', db_filename)
            shutil.copy2(output_js, backup_js)
        except Exception as e:
            print(f"Error saving backup search db: {e}")

        # CẬP NHẬT TRẠNG THÁI QUÉT VÀO SSFolder.txt
        try:
            ss_folder_file = os.path.join(self.base_dir, 'data', 'SSFolder.txt')
            scanned_dict = {}
            if os.path.exists(ss_folder_file):
                with open(ss_folder_file, 'r', encoding='utf-8') as f:
                    try:
                        scanned_dict = json.loads(f.read().strip())
                    except Exception:
                        scanned_dict = {}
            
            # Chuẩn hóa đường dẫn
            normalized_path = os.path.normpath(scan_target)
            scanned_dict[normalized_path] = len(db_entries)
            
            with open(ss_folder_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(scanned_dict, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Error updating SSFolder.txt: {e}")

        return {
            "success": True,
            "new_files": new_files_count,
            "total_entries": len(db_entries),
            "errors": scan_errors[:50],
            "error_count": len(scan_errors)
        }

def main():
    # Xác định thư mục gốc chính xác
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    api = Api(base_dir)
    
    html_path = os.path.join(base_dir, 'data', 'SuperSearch.html')
    
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
