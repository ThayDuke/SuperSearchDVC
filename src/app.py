import os
import sys
import hashlib
import json
import shutil
import threading
import time
import subprocess
import re
import importlib.util
from importlib.metadata import version as package_version
from concurrent.futures import ThreadPoolExecutor

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

# Import pandas tslibs first to work around circular import in frozen environment
try:
    import pandas._libs.tslibs.np_datetime
except Exception:
    pass

import webview
from markitdown import (
    StreamInfo,
    UnsupportedFormatException,
    MissingDependencyException,
)

# Core utilities and safety rails
from core_utils import (
    LOCAL_CORE_FORMAT_GROUPS,
    SUPPORTED_EXTENSIONS,
    IMAGE_EXTENSIONS,
    FORMAT_DEPENDENCIES,
    DEFAULT_SOURCE_LIMIT_BYTES,
    IMAGE_SOURCE_LIMIT_BYTES,
    ZIP_SOURCE_LIMIT_BYTES,
    ZIP_MAX_ENTRIES,
    ZIP_MAX_ENTRY_BYTES,
    ZIP_MAX_TOTAL_BYTES,
    ZIP_MAX_COMPRESSION_RATIO,
    ZIP_MAX_DEPTH,
    safe_long_path,
    open_file_with_retry,
    run_with_timeout,
    remove_diacritics,
    MEMORYSTATUSEX,
    get_system_ram_load,
    get_safe_workers_count,
    ConversionPolicyError,
    DynamicWorkerRegulator,
)

# Document converters
from converters import (
    configure_tesseract,
    LocalOcrPdfConverter,
    LocalOcrImageConverter,
    LocalDocConverter,
    LocalXlsConverter,
    SafeZipConverter,
    create_markdown_converter,
)

# File classification and scoring heuristics
from file_classifier import (
    clean_content,
    is_ocr_noise,
    infer_original_ext,
    calculate_ocr_quality_score,
    classify_source,
    classify_file,
    detect_domain,
    detect_doc_type,
    detect_language,
    get_file_creation_parts,
)

from index_store import IndexStore, normalize_search_text, extract_headings

try:
    from folder_watchdog import FolderWatchdog
except ImportError:
    FolderWatchdog = None

try:
    from gemini_ocr_engine import test_gemini_connection
except ImportError:
    test_gemini_connection = None

try:
    from html_builder import build_html_document, markdown_to_html_body
except ImportError:
    build_html_document = None
    markdown_to_html_body = None


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
        self.runtime_html_root = os.path.join(self.runtime_dir, 'HTML')
        os.makedirs(self.runtime_html_root, exist_ok=True)
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
        self.ocr_lock = threading.BoundedSemaphore(2)
        self.gemini_api_key = ''
        self.gemini_model = 'gemini-3.6-flash'
        self.ocr_engine = 'hybrid'
        self.load_saved_ocr_config()
        self.watchdog = FolderWatchdog(debounce_seconds=2.5) if FolderWatchdog else None
        self._task_weights = {}
        self._task_subprogress = {}
        self._completed_weights = 0.0
        self._last_progress_report_time = 0.0
        self._cleanup_stale_temp_files()

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
            cfg = {}
            if os.path.exists(self.runtime_config_file):
                with open(self.runtime_config_file, 'r', encoding='utf-8') as f:
                    try:
                        cfg = json.load(f)
                    except Exception:
                        cfg = {}
            cfg['scan_dir'] = path.strip()
            temp_path = self.runtime_config_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.runtime_config_file)
            self.scan_dir = os.path.normpath(path)
            return True
        except Exception as e:
            print(f"Error saving scan_dir: {e}")
            return False

    def load_saved_ocr_config(self):
        try:
            if os.path.exists(self.runtime_config_file):
                with open(self.runtime_config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.gemini_api_key = str(cfg.get('gemini_api_key') or '').strip()
                    self.gemini_model = str(cfg.get('gemini_model') or 'gemini-3.6-flash').strip()
                    self.ocr_engine = str(cfg.get('ocr_engine') or 'hybrid').strip()
        except Exception as e:
            print(f"Error loading ocr config: {e}")

    def get_ocr_config(self):
        return {
            'gemini_api_key': self.gemini_api_key,
            'gemini_model': self.gemini_model,
            'ocr_engine': self.ocr_engine,
        }

    def save_ocr_config(self, gemini_api_key, gemini_model='gemini-3.6-flash', ocr_engine='hybrid'):
        try:
            os.makedirs(self.runtime_dir, exist_ok=True)
            cfg = {}
            if os.path.exists(self.runtime_config_file):
                with open(self.runtime_config_file, 'r', encoding='utf-8') as f:
                    try:
                        cfg = json.load(f)
                    except Exception:
                        cfg = {}
            cfg['gemini_api_key'] = (gemini_api_key or '').strip()
            cfg['gemini_model'] = (gemini_model or 'gemini-3.6-flash').strip()
            cfg['ocr_engine'] = (ocr_engine or 'hybrid').strip()

            temp_path = self.runtime_config_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.runtime_config_file)

            self.gemini_api_key = cfg['gemini_api_key']
            self.gemini_model = cfg['gemini_model']
            self.ocr_engine = cfg['ocr_engine']
            return {'success': True, 'message': 'Đã lưu cấu hình OCR thành công.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def test_gemini_api_key(self, gemini_api_key, gemini_model='gemini-3.6-flash'):
        if test_gemini_connection is None:
            return {'success': False, 'message': 'Module gemini_ocr_engine chưa được nạp.'}
        success, msg = test_gemini_connection(gemini_api_key, gemini_model)
        return {'success': success, 'message': msg}

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
        return get_system_ram_load()

    def get_safe_workers_count(self):
        return get_safe_workers_count()

    def search_documents(self, query='', page=1, page_size=50, filters=None):
        return self.index_store.search_documents(query, page, page_size, filters)

    def get_runtime_capabilities(self):
        """Expose the backend features expected by the external HTML UI."""
        try:
            from export_service import DOCX_AVAILABLE
        except Exception:
            DOCX_AVAILABLE = False
        return {
            "api_version": 2,
            "export_document": True,
            "export_docx": bool(DOCX_AVAILABLE),
            "export_markdown": True,
            "open_document_location": True,
            "spelling_suggestion": True,
        }

    def get_document(self, document_id):
        doc = self.index_store.get_document(document_id)
        if doc and isinstance(doc, dict):
            if markdown_to_html_body is not None and doc.get('content'):
                doc['html_content'] = markdown_to_html_body(doc['content'])
            else:
                doc['html_content'] = ''
        return doc

    def export_document(self, document_id, format_type='docx', custom_output_dir=None):
        """Export document by document_id to docx or markdown."""
        doc = self.index_store.get_document(document_id)
        if not doc:
            return {"success": False, "error": "Không tìm thấy tài liệu trong cơ sở dữ liệu."}

        format_type = str(format_type or 'docx').lower().strip()
        export_dir = custom_output_dir or os.path.join(self.base_dir, 'runtime', 'exports')
        os.makedirs(export_dir, exist_ok=True)

        safe_title = re.sub(r'[\\/*?:"<>|]', '_', doc.get('title') or 'document')[:60].strip()
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        try:
            if format_type in ('md', 'markdown'):
                filename = f"{safe_title}_{timestamp}.md"
                out_path = os.path.join(export_dir, filename)
                temp_path = os.path.join(export_dir, f".{filename}.{os.getpid()}.tmp")
                from export_service import export_to_markdown
                export_to_markdown(doc, temp_path)
                os.replace(temp_path, out_path)
                return {"success": True, "path": out_path, "filename": filename, "format": "md"}
            elif format_type in ('docx', 'word'):
                filename = f"{safe_title}_{timestamp}.docx"
                out_path = os.path.join(export_dir, filename)
                temp_path = os.path.join(export_dir, f".{filename}.{os.getpid()}.tmp")
                from export_service import export_to_docx
                export_to_docx(doc, temp_path)
                os.replace(temp_path, out_path)
                return {"success": True, "path": out_path, "filename": filename, "format": "docx"}
            else:
                return {"success": False, "error": f"Định dạng xuất không được hỗ trợ: {format_type}"}
        except Exception as exc:
            for candidate in (locals().get("temp_path"),):
                if candidate:
                    try:
                        os.remove(candidate)
                    except OSError:
                        pass
            return {"success": False, "error": f"Lỗi khi xuất tệp: {str(exc)}"}

    def get_page_preview_image(self, document_id, page_number=1):
        """Extracts and renders a page image for side-by-side comparison in Quick View."""
        doc = self.index_store.get_document(document_id)
        if not doc:
            return {"success": False, "error": "Không tìm thấy tài liệu trong cơ sở dữ liệu."}

        orig_path = doc.get("absolute_original_path") or doc.get("original_path") or ""
        resolved_path = None
        if hasattr(self.index_store, "resolve_file_path"):
            resolved_path = self.index_store.resolve_file_path(orig_path)
        if not resolved_path:
            resolved_path = safe_long_path(orig_path)

        if not os.path.isfile(resolved_path):
            return {"success": False, "error": f"Không tìm thấy tệp gốc: {orig_path}"}

        ext = os.path.splitext(resolved_path)[1].lower()

        # Handle image formats
        if ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff'):
            try:
                with open(resolved_path, "rb") as f:
                    raw_bytes = f.read()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                import base64
                b64 = base64.b64encode(raw_bytes).decode("ascii")
                return {
                    "success": True,
                    "image_base64": b64,
                    "mime_type": mime,
                    "current_page": 1,
                    "total_pages": 1,
                    "is_single_image": True,
                }
            except Exception as e:
                return {"success": False, "error": f"Lỗi đọc hình ảnh: {str(e)}"}

        # Handle PDF files
        if ext == '.pdf':
            try:
                mtime = os.path.getmtime(resolved_path)
            except Exception:
                mtime = 0
            page_idx_target = max(1, int(page_number or 1))
            cache_key = (resolved_path, page_idx_target, mtime)
            with self.lock:
                if hasattr(self, '_page_preview_cache') and cache_key in self._page_preview_cache:
                    return self._page_preview_cache[cache_key]

            try:
                import pdfplumber
                import io
                import base64
                from PIL import Image

                with pdfplumber.open(resolved_path) as pdf:
                    total_pages = len(pdf.pages)
                    if total_pages == 0:
                        return {"success": False, "error": "Tệp PDF không chứa trang nào."}

                    page_idx = max(1, min(page_idx_target, total_pages))
                    target_page = pdf.pages[page_idx - 1]

                    page_img = target_page.to_image(resolution=150)
                    rgb_img = page_img.original
                    if rgb_img.mode in ("RGBA", "P", "LA"):
                        rgb_img = rgb_img.convert("RGB")

                    buf = io.BytesIO()
                    rgb_img.save(buf, format="JPEG", quality=85)
                    rendered_bytes = buf.getvalue()
                    del page_img, rgb_img, buf

                    b64 = base64.b64encode(rendered_bytes).decode("ascii")
                    res = {
                        "success": True,
                        "image_base64": b64,
                        "mime_type": "image/jpeg",
                        "current_page": page_idx,
                        "total_pages": total_pages,
                        "is_single_image": False,
                    }

                    with self.lock:
                        if not hasattr(self, '_page_preview_cache'):
                            self._page_preview_cache = {}
                            self._preview_cache_order = []
                        if cache_key not in self._page_preview_cache:
                            if len(self._preview_cache_order) >= 15:
                                oldest = self._preview_cache_order.pop(0)
                                self._page_preview_cache.pop(oldest, None)
                            self._page_preview_cache[cache_key] = res
                            self._preview_cache_order.append(cache_key)

                    return res
            except Exception as e:
                return {"success": False, "error": f"Lỗi trích xuất trang PDF: {str(e)}"}

        return {
            "success": False,
            "error": "Chế độ đối chiếu 1:1 chỉ hỗ trợ tệp PDF và Hình ảnh scan.",
            "is_supported": False,
        }

    def enable_watchdog(self, folder_path=None):
        """Enable background real-time folder monitoring."""
        if not self.watchdog:
            return {"success": False, "error": "FolderWatchdog không khả dụng trên hệ thống."}
        target = folder_path or getattr(self, 'scan_dir', None)
        if not target or not os.path.isdir(target):
            return {"success": False, "error": "Chưa chọn thư mục hợp lệ để theo dõi."}
        try:
            self.watchdog.start(
                target,
                self._on_watchdog_changes,
                on_overflow_callback=self._on_watchdog_overflow,
            )
            return {"success": True, "folder": target}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _on_watchdog_overflow(self):
        """Callback invoked when Watchdog buffer overflows; triggers incremental scan."""
        print("[Watchdog] Phát hiện tràn bộ đệm sự kiện (overflow). Đang kích hoạt đồng bộ bù...")
        target = self.watchdog.watch_folder if self.watchdog else getattr(self, 'scan_dir', None)
        if target and os.path.isdir(target):
            threading.Thread(target=self.scan_and_index, daemon=True).start()

    def _cleanup_stale_temp_files(self):
        """Clean up orphaned .tmp-* and .staging-* files from aborted prior sessions."""
        try:
            if not os.path.exists(self.runtime_dir):
                return
            for root, dirs, files in os.walk(self.runtime_dir):
                for f in files:
                    if ".tmp-" in f or f.endswith(".tmp"):
                        fp = os.path.join(root, f)
                        try:
                            if time.time() - os.path.getmtime(fp) > 60:
                                os.remove(fp)
                        except Exception:
                            pass
                for d in list(dirs):
                    if d.startswith(".staging-"):
                        dp = os.path.join(root, d)
                        try:
                            shutil.rmtree(dp, ignore_errors=True)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Cleanup Warning] Error cleaning stale temp files: {e}")

    def disable_watchdog(self):
        """Disable background folder monitoring."""
        if self.watchdog:
            self.watchdog.stop()
        return {"success": True}

    def get_watchdog_status(self):
        """Returns the current watchdog status."""
        if not self.watchdog:
            return {"enabled": False, "folder": None, "available": False}
        return {
            "enabled": self.watchdog.is_running,
            "folder": self.watchdog.watch_folder,
            "available": True,
        }

    def _on_watchdog_changes(self, changed_paths, deleted_paths):
        """Callback invoked by FolderWatchdog when files change."""
        print(f"[Watchdog] Phát hiện {len(changed_paths)} tệp thay đổi, {len(deleted_paths)} tệp bị xóa.")
        threading.Thread(
            target=self._run_watchdog_sync,
            args=(list(changed_paths), list(deleted_paths)),
            daemon=True,
        ).start()

    def _get_or_create_md_converter(self):
        if not hasattr(self, '_md_converter') or self._md_converter is None:
            self._md_converter = create_markdown_converter(self)
        return self._md_converter

    @staticmethod
    def _run_conversion_with_timeout_policy(operation, extension):
        """Run OCR PDFs cooperatively; retain a hard timeout for other formats."""
        if str(extension or "").lower() == ".pdf":
            return operation()
        return run_with_timeout(operation, timeout=60)

    def _scan_worker_count(self, tasks):
        """Cap concurrent PDF OCR to avoid memory pressure and API fan-out."""
        workers = self.get_safe_workers_count()
        if any(os.path.splitext(task.get("src_path", ""))[1].lower() == ".pdf" for task in tasks):
            return min(workers, 2)
        return workers

    def convert_file_to_markdown(self, file_path):
        """Convert one document with cooperative PDF cancellation and bounded non-PDF work."""
        target_path = safe_long_path(file_path)
        if not os.path.isfile(target_path):
            return ""
        try:
            converter = self._get_or_create_md_converter()
            ext = os.path.splitext(file_path)[1].lower()

            def do_convert():
                if ext == ".zip":
                    with open_file_with_retry(file_path, "rb") as archive_stream:
                        result = SafeZipConverter(converter).convert(
                            archive_stream,
                            StreamInfo(
                                extension=".zip",
                                filename=os.path.basename(file_path),
                                local_path=target_path,
                            ),
                        )
                else:
                    result = converter.convert_local(target_path)
                return (result.text_content or "").strip()

            text = self._run_conversion_with_timeout_policy(do_convert, ext)
            if text and text.lower().startswith("error during local"):
                return ""
            return text or ""
        except Exception as e:
            print(f"[Conversion Error] {file_path}: {e}")
            return ""

    def _convert_document_to_markdown(self, file_path):
        """Internal alias for converting a single document to Markdown text."""
        return self.convert_file_to_markdown(file_path)

    def _run_watchdog_sync(self, changed_paths, deleted_paths):
        """Syncs debounced changes into SQLite index incrementally."""
        if not self.watchdog or not self.watchdog.watch_folder:
            return
        scan_target = self.watchdog.watch_folder
        scan_id = self._scan_id(scan_target)

        entries_to_sync = []
        for file_path in changed_paths:
            if not os.path.isfile(file_path):
                continue
            try:
                converted_text = self.convert_file_to_markdown(file_path)
                if not converted_text:
                    continue
                rel_path = os.path.relpath(file_path, scan_target)
                filename = os.path.basename(file_path)
                file_year, file_month = self._get_file_creation_parts(file_path)
                title_clean = remove_diacritics(filename)
                content_clean = remove_diacritics(converted_text)
                headings_clean = normalize_search_text(extract_headings(converted_text))
                word_count = len(converted_text.split()) if converted_text else 1
                ocr_quality_score = self._calculate_ocr_quality_score(converted_text)
                source_type = self._classify_source(filename, rel_path, converted_text, ocr_quality_score)
                source_signature = self._source_signature(file_path)

                entry = {
                    "scan_id": scan_id,
                    "title": filename,
                    "title_clean": title_clean,
                    "headings_clean": headings_clean,
                    "path": rel_path.replace("\\", "/"),
                    "original_path": rel_path.replace("\\", "/"),
                    "absolute_original_path": os.path.abspath(file_path),
                    "domain": "Tài liệu chung",
                    "doc_type": "Tài liệu",
                    "language": self._detect_language(converted_text),
                    "year": str(file_year) if file_year else "N/A",
                    "file_year": file_year,
                    "file_month": file_month,
                    "source_type": source_type,
                    "ocr_quality_score": ocr_quality_score,
                    "wordCount": word_count,
                    "source_size": source_signature["size"] if source_signature else 0,
                    "source_mtime_ns": source_signature["mtime_ns"] if source_signature else 0,
                    "source_sha256": source_signature.get("sha256") if source_signature else None,
                    "content": converted_text,
                    "content_clean": content_clean,
                }
                entries_to_sync.append(entry)
            except Exception as e:
                print(f"[Watchdog Sync Error] {file_path}: {e}")

        if entries_to_sync:
            try:
                self.index_store.sync_entries(entries_to_sync, scan_id=scan_id, delete_missing=False)
            except Exception as db_err:
                print(f"[Watchdog DB Sync Error]: {db_err}")

        if deleted_paths:
            try:
                self.index_store.delete_entries_by_paths(deleted_paths, scan_id=scan_id)
            except Exception as del_err:
                print(f"[Watchdog DB Delete Error]: {del_err}")

        if self._window:
            try:
                c_count = len(entries_to_sync)
                d_count = len(deleted_paths)
                self._window.evaluate_js(
                    f"if (typeof onWatchdogSyncSuccess === 'function') onWatchdogSyncSuccess({c_count}, {d_count});"
                )
            except Exception:
                pass

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

    def _recalculate_and_report_progress(self):
        """Calculates weighted progress based on bytes, completed tasks, and active subprogress."""
        if not getattr(self, '_task_weights', None):
            return
        active_sub_sum = sum(
            self._task_weights.get(tid, 0.0) * self._task_subprogress.get(tid, 0.0)
            for tid in list(self._task_subprogress.keys())
        )
        total_fraction = self._completed_weights + active_sub_sum
        percent = min(98, max(2, round(2 + 96 * total_fraction)))
        active_list = self.active_files[:4]
        self._report_progress(percent, active_list)

    def update_task_subprogress(self, file_path, fraction=0.0, status_text=None):
        """Reports intra-item progress for multi-page documents (e.g. PDF OCR pages)."""
        if not file_path:
            return
        task_id = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))
        with self.lock:
            if hasattr(self, '_task_subprogress'):
                self._task_subprogress[task_id] = max(0.0, min(1.0, fraction))
            for item in self.active_files:
                if item["id"] == task_id:
                    if status_text:
                        item["status"] = status_text
                    break
            now = time.time()
            if getattr(self, '_last_progress_report_time', 0.0) + 0.1 <= now:
                self._last_progress_report_time = now
                self._recalculate_and_report_progress()

    @staticmethod
    def _clean_explorer_path(path):
        """Convert Windows long-path syntax to the form Explorer accepts."""
        value = str(path or "").strip()
        if value.startswith("\\\\?\\UNC\\"):
            return "\\\\" + value[8:]
        if value.startswith("\\\\?\\"):
            return value[4:]
        return value

    def _open_explorer_resolved(self, resolved):
        clean_resolved = self._clean_explorer_path(resolved)
        if os.path.isfile(resolved) or os.path.isfile(clean_resolved):
            # Keep /select, and the file path as separate argv values. Folding
            # them into one value breaks Explorer parsing for paths containing
            # commas (for example "Global Success, tập một.pdf") and Explorer
            # silently opens Documents instead.
            subprocess.Popen(['explorer.exe', '/select,', clean_resolved])
            return {"success": True, "action": "selected_file", "path": clean_resolved}
        if os.path.isdir(resolved) or os.path.isdir(clean_resolved):
            subprocess.Popen(['explorer.exe', clean_resolved])
            return {"success": True, "action": "opened_parent", "path": clean_resolved}
        # Explorer silently falls back to Documents for a non-existent
        # /select target. Never open that misleading default.
        return {"success": False, "action": "not_found", "path": clean_resolved,
                "error": "Không tìm thấy file gốc hoặc thư mục cha."}

    def _find_scan_file_by_name(self, filename):
        """Recover legacy paths by matching the source filename in scan_dir."""
        scan_dir = getattr(self, "scan_dir", "")
        name = os.path.basename(str(filename or "").strip())
        if not scan_dir or not name or not os.path.isdir(scan_dir):
            return None
        try:
            for root, _dirs, files in os.walk(scan_dir):
                for candidate in files:
                    if candidate.casefold() == name.casefold():
                        return os.path.normpath(os.path.join(root, candidate))
        except OSError:
            return None
        return None

    def open_document_location(self, document_id):
        """Resolve a document from SQLite and open its original file in Explorer."""
        doc = self.index_store.get_document(document_id)
        if not doc:
            return {"success": False, "action": "not_found", "error": "Không tìm thấy tài liệu trong cơ sở dữ liệu."}
        original = doc.get("absolute_original_path") or doc.get("original_path") or ""
        if not original:
            return {"success": False, "action": "not_found", "error": "Tài liệu không có đường dẫn file gốc."}
        relative = str(doc.get("original_path") or "").strip()
        candidates = []
        if relative and not os.path.isabs(relative) and getattr(self, "scan_dir", ""):
            candidates.append(os.path.normpath(os.path.join(self.scan_dir, relative)))
        candidates.append(os.path.normpath(str(original).strip()))
        resolved = next((candidate for candidate in candidates if os.path.exists(candidate)), None)
        if not resolved:
            resolved = self.index_store.resolve_file_path(original) or candidates[0]
        if not os.path.exists(resolved):
            resolved = self._find_scan_file_by_name(original) or resolved
        return self._open_explorer_resolved(resolved)

    def open_explorer(self, path):
        if not path:
            return False
        path_str = str(path).strip()
        # Legacy index entries may only expose a relative original_path and
        # the HTML fallback calls this method without a document_id. Resolve
        # that path against the user's scan folder before consulting the
        # process working directory (which is commonly My Documents).
        resolved = None
        if not os.path.isabs(path_str) and getattr(self, "scan_dir", ""):
            scan_candidate = os.path.normpath(os.path.join(self.scan_dir, path_str))
            if os.path.exists(scan_candidate):
                resolved = scan_candidate
        if hasattr(self, 'index_store') and hasattr(self.index_store, 'resolve_file_path'):
            resolved = resolved or self.index_store.resolve_file_path(path_str)
        if not resolved:
            resolved = os.path.normpath(path_str)
        if not os.path.exists(resolved):
            resolved = self._find_scan_file_by_name(path_str) or resolved

        return bool(self._open_explorer_resolved(resolved).get("success"))

    # Forwarding classification helpers
    def _clean_content(self, content):
        return clean_content(content)

    def _is_ocr_noise(self, text):
        return is_ocr_noise(text)

    def _infer_original_ext(self, path):
        return infer_original_ext(path)

    def _calculate_ocr_quality_score(self, text):
        return calculate_ocr_quality_score(text)

    def _classify_source(self, filepath, rel_path, content, ocr_quality_score):
        return classify_source(filepath, rel_path, content, ocr_quality_score)

    def _classify_file(self, filepath, relative_path):
        return classify_file(filepath, relative_path)

    def _detect_domain(self, filepath, rel_path, content_lower):
        return detect_domain(filepath, rel_path, content_lower)

    def _detect_doc_type(self, filepath, rel_path, content_lower):
        return detect_doc_type(filepath, rel_path, content_lower)

    def _detect_language(self, content_lower):
        return detect_language(content_lower)

    def _get_file_creation_parts(self, path):
        return get_file_creation_parts(path)

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
            for key in ("ORIGINAL_PATH", "SCAN_TARGET", "SOURCE_SIZE", "SOURCE_MTIME_NS", "SOURCE_SHA256", "OCR_CONFIG"):
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
            if self._source_signature(source_path, include_hash=True).get("sha256") != stored_hash:
                return True
        except (TypeError, ValueError):
            return True

        ext = self._infer_original_ext(source_path)
        if ext in IMAGE_EXTENSIONS or ext == '.pdf':
            has_gemini = bool(getattr(self, 'gemini_api_key', ''))
            engine = getattr(self, 'ocr_engine', 'hybrid')
            model = getattr(self, 'gemini_model', 'gemini-3.6-flash')
            current_tag = f"{engine}:{model}" if has_gemini else "local"
            stored_tag = metadata.get("OCR_CONFIG", "")
            if has_gemini and engine in ('hybrid', 'gemini'):
                if not stored_tag or "gemini" not in stored_tag or stored_tag != current_tag:
                    return True

        return False

    def _html_cache_path(self, directory, source_path):
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(source_path)))
        identity = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]
        return os.path.join(directory, f"{os.path.basename(source_path)}.{identity}.html")

    def _write_html(self, path, markdown_content, source_path, scan_target):
        if build_html_document is None:
            return
        try:
            title = os.path.splitext(os.path.basename(source_path))[0]
            html_doc = build_html_document(markdown_content, title=title, original_path=source_path)
            temp_path = f"{path}.tmp-{os.getpid()}-{threading.get_ident()}"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(temp_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(html_doc)
            os.replace(temp_path, path)
        except Exception as e:
            print(f"Warning: Failed to write HTML document {path}: {e}")

    def _write_markdown(self, path, content, source_path, scan_target):
        source = self._source_signature(source_path, include_hash=True) or {"size": 0, "mtime_ns": 0, "sha256": ""}
        body = content or ""
        body = re.sub(r'^<!--\s*(?:ORIGINAL_PATH|SCAN_TARGET|SOURCE_SIZE|SOURCE_MTIME_NS|SOURCE_SHA256|OCR_CONFIG):.*?-->\s*\n?', '', body, flags=re.MULTILINE)
        has_gemini = bool(getattr(self, 'gemini_api_key', ''))
        engine = getattr(self, 'ocr_engine', 'hybrid')
        model = getattr(self, 'gemini_model', 'gemini-3.6-flash')
        ocr_tag = f"{engine}:{model}" if has_gemini else "local"
        header = (
            f"<!-- ORIGINAL_PATH: {os.path.abspath(source_path)} -->\n"
            f"<!-- SCAN_TARGET: {os.path.abspath(scan_target)} -->\n"
            f"<!-- SOURCE_SIZE: {source['size']} -->\n"
            f"<!-- SOURCE_MTIME_NS: {source['mtime_ns']} -->\n"
            f"<!-- SOURCE_SHA256: {source.get('sha256', '')} -->\n"
            f"<!-- OCR_CONFIG: {ocr_tag} -->\n\n"
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
        if isinstance(error, TimeoutError):
            return "timeout"
        if isinstance(error, PermissionError):
            return "file_locked"
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
            md_converter = self._get_or_create_md_converter()
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

        # Tiền kiểm tra dung lượng đĩa trống
        try:
            free_bytes = shutil.disk_usage(self.runtime_dir).free
            if free_bytes < 300 * 1024 * 1024:
                return {
                    "success": False,
                    "error": f"Dung lượng đĩa trống quá thấp ({free_bytes // (1024 * 1024)} MB). Cần tối thiểu 300 MB đĩa trống để đảm bảo an toàn.",
                }
        except Exception:
            pass

        # Thư mục chỉ mục runtime
        app_markdown_root = self.runtime_markdown_root
        os.makedirs(app_markdown_root, exist_ok=True)

        scan_id = self._scan_id(scan_target)
        dest_folder_md_root = os.path.join(app_markdown_root, scan_id)
        os.makedirs(dest_folder_md_root, exist_ok=True)
        dest_folder_html_root = os.path.join(self.runtime_html_root, scan_id)
        os.makedirs(dest_folder_html_root, exist_ok=True)
        staging_root = os.path.join(self.runtime_dir, f".staging-{scan_id}-{os.getpid()}")
        if os.path.exists(staging_root):
            shutil.rmtree(staging_root, ignore_errors=True)
        os.makedirs(staging_root, exist_ok=True)

        expected_markdown_files = set()
        tasks = []
        managed_dirs = self._managed_source_dirs(scan_target)

        # Quét thư mục nguồn (chỉ đọc, KHÔNG ghi vào scan_target)
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
                            'scan_target': scan_target,
                            'size': source_size,
                        })

        total_tasks = len(tasks)
        total_bytes = sum(t.get('size', 1024) for t in tasks)
        completed_tasks = 0

        self._scan_paused = False
        self._scan_aborted = False
        self._pause_event.set()

        with self.lock:
            self._task_weights = {}
            self._task_subprogress = {}
            self._completed_weights = 0.0
            self._last_progress_report_time = 0.0
            for t in tasks:
                t_id = os.path.normcase(os.path.normpath(os.path.abspath(t['src_path'])))
                t_size = t.get('size', 1024)
                if total_bytes > 0 and total_tasks > 0:
                    weight = 0.70 * (t_size / total_bytes) + 0.30 * (1.0 / total_tasks)
                elif total_tasks > 0:
                    weight = 1.0 / total_tasks
                else:
                    weight = 0.0
                self._task_weights[t_id] = weight
                self._task_subprogress[t_id] = 0.0

        if total_tasks > 0:
            self._report_progress(2, [])

        workers = self._scan_worker_count(tasks)
        regulator = DynamicWorkerRegulator(self.get_system_ram_load, base_workers=workers)

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
                self._recalculate_and_report_progress()

            if not regulator.acquire(abort_check=lambda: self._scan_aborted):
                with self.lock:
                    self.active_files = [f for f in self.active_files if f["id"] != task_id]
                    completed_tasks += 1
                    self._completed_weights += self._task_weights.get(task_id, 0.0)
                    self._task_subprogress.pop(task_id, None)
                    self._recalculate_and_report_progress()
                return

            try:
                success = False
                try:
                    with self.lock:
                        for item in self.active_files:
                            if item["id"] == task_id:
                                item["status"] = "Working"
                                break
                        self._recalculate_and_report_progress()

                    def do_convert_task():
                        if os.path.splitext(src_path)[1].lower() == ".zip":
                            with open_file_with_retry(src_path, "rb") as archive_stream:
                                return SafeZipConverter(md_converter).convert(
                                    archive_stream,
                                    StreamInfo(
                                        extension=".zip",
                                        filename=os.path.basename(src_path),
                                        local_path=safe_long_path(src_path),
                                    ),
                                )
                        else:
                            return md_converter.convert_local(safe_long_path(src_path))

                    result = self._run_conversion_with_timeout_policy(
                        do_convert_task,
                        os.path.splitext(src_path)[1].lower(),
                    )

                    if self._scan_aborted:
                        with self.lock:
                            self.active_files = [f for f in self.active_files if f["id"] != task_id]
                            completed_tasks += 1
                            self._completed_weights += self._task_weights.get(task_id, 0.0)
                            self._task_subprogress.pop(task_id, None)
                            self._recalculate_and_report_progress()
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
                        self._completed_weights += self._task_weights.get(task_id, 0.0)
                        self._task_subprogress.pop(task_id, None)
                        self._recalculate_and_report_progress()
                    return

                with self.lock:
                    self.active_files = [f for f in self.active_files if f["id"] != task_id]
                    if success:
                        new_files_count += 1
                    completed_tasks += 1
                    self._completed_weights += self._task_weights.get(task_id, 0.0)
                    self._task_subprogress.pop(task_id, None)
                    self._recalculate_and_report_progress()
            finally:
                regulator.release()

        if total_tasks > 0:
            self.executor = ThreadPoolExecutor(max_workers=workers)
            try:
                self.executor.map(run_single_task, tasks)
            finally:
                if self.executor:
                    wait_threads = not self._scan_aborted
                    self.executor.shutdown(wait=wait_threads)
                    self.executor = None

        if self._scan_aborted:
            shutil.rmtree(staging_root, ignore_errors=True)
            self._report_progress(0, [])
            return {"success": False, "error": "Đã hủy quét tài liệu"}

        for task in tasks:
            stage_path = task['stage_md_path']
            if os.path.exists(stage_path):
                os.makedirs(os.path.dirname(task['dest_md_path']), exist_ok=True)
                os.replace(stage_path, task['dest_md_path'])
        shutil.rmtree(staging_root, ignore_errors=True)

        orphaned_markdown_files = []
        for root, dirs, files in os.walk(dest_folder_md_root):
            for file in files:
                if file.lower().endswith('.md'):
                    md_path = os.path.normpath(os.path.join(root, file))
                    if md_path not in expected_markdown_files:
                        orphaned_markdown_files.append(md_path)

        self._report_progress(100, [])

        # Quét toàn bộ thư mục MARKDOWN tập trung để lập chỉ mục
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

                            cand_scan = os.path.normpath(os.path.join(scan_target, original_filename))
                            cand_base = os.path.normpath(os.path.join(self.base_dir, original_rel_path))
                            # The scanned folder is the source of truth. The EXE
                            # directory may itself be Documents and must not win
                            # over an existing file in scan_target.
                            if os.path.exists(cand_scan):
                                absolute_original_path = cand_scan
                            elif os.path.exists(cand_base):
                                absolute_original_path = cand_base
                            else:
                                absolute_original_path = cand_base

                        file_year, file_month = self._get_file_creation_parts(absolute_original_path)

                        title_clean = remove_diacritics(original_filename)
                        content_clean = remove_diacritics(cleaned_content)
                        word_count = len(cleaned_content.split()) if cleaned_content else 1
                        year = str(file_year) if file_year else "N/A"
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

        try:
            deduped_entries = []
            seen_keys = {}

            def entry_quality(entry):
                quality = float(entry.get("ocr_quality_score") or 0)
                words = int(entry.get("wordCount") or 0)
                return (quality, words)

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
            error_summary = self._error_summary(scan_errors)
            error_details = ", ".join(f"{code}: {count}" for code, count in sorted(error_summary.items()))
            error_message = "Không tạo được tài liệu tìm kiếm từ các tệp nguồn."
            if error_details:
                error_message += f" Chi tiết: {error_details}."
            return {
                "success": False,
                "error": error_message,
                "new_files": new_files_count,
                "total_entries": self.index_store.count_documents(),
                "errors": scan_errors[:50],
                "error_count": len(scan_errors),
                "error_summary": error_summary,
            }

        output_js = self.runtime_search_db
        output_tmp = f"{output_js}.tmp-{os.getpid()}"
        status_tmp = f"{self.runtime_status_file}.tmp-{os.getpid()}"
        try:
            with open(output_tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write("var SEARCH_DB = [];\n")

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

        def _safe_replace_file(src, dst, max_retries=5, delay=0.15):
            for attempt in range(max_retries):
                try:
                    os.replace(src, dst)
                    return
                except OSError:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay)

        try:
            self.index_store.sync_entries(db_entries, scan_id=scan_id)
            _safe_replace_file(output_tmp, output_js)
            _safe_replace_file(status_tmp, self.runtime_status_file)
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
                "error": f"Lỗi lưu trữ chỉ mục: {e}",
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
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    api = Api(base_dir)

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

    file_url = 'file:///' + os.path.abspath(html_path).replace('\\', '/')

    width = 960
    height = 540

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
