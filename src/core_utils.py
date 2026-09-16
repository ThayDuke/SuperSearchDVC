import os
import sys
import time
import threading
import gc
import ctypes
import unicodedata

# Format constants
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


def safe_long_path(path: str) -> str:
    """Normalize path with Windows extended-length prefix (\\\\?\\) if path length >= 240."""
    if not path or not isinstance(path, str):
        return path
    if sys.platform.startswith("win"):
        norm = os.path.normpath(path)
        if len(norm) >= 240 and not norm.startswith(("\\\\?\\", "\\\\.\\")):
            if norm.startswith("\\\\"):
                return "\\\\?\\UNC\\" + norm[2:]
            return "\\\\?\\" + os.path.abspath(norm)
        return norm
    return path


def open_file_with_retry(file_path: str, mode="rb", max_retries=3, initial_delay=0.3):
    """Open file with retry on Windows Sharing Violation (WinError 32 / PermissionError)."""
    target = safe_long_path(file_path)
    for attempt in range(max_retries):
        try:
            return open(target, mode)
        except PermissionError as pe:
            if attempt < max_retries - 1:
                time.sleep(initial_delay * (2 ** attempt))
            else:
                raise pe


def run_with_timeout(func, args=(), kwargs=None, timeout=60):
    """Execute a function in a daemon thread with timeout to prevent worker hangs."""
    if kwargs is None:
        kwargs = {}
    result_container = []
    error_container = []

    def worker():
        try:
            result_container.append(func(*args, **kwargs))
        except Exception as ex:
            error_container.append(ex)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        raise TimeoutError(f"Tác vụ vượt quá thời gian tối đa {timeout} giây.")
    if error_container:
        raise error_container[0]
    return result_container[0] if result_container else None


def remove_diacritics(text: str) -> str:
    """Remove Vietnamese diacritics and normalize to lowercase ASCII."""
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    no_marks = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    cleaned = no_marks.replace('đ', 'd').replace('Đ', 'D')
    return cleaned.lower()


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


def get_system_ram_load() -> int:
    """Get current RAM load percentage via Windows GlobalMemoryStatusEx API."""
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.dwMemoryLoad
    except Exception:
        return 50  # fallback safe value if ctypes fails


def get_safe_workers_count(base_workers=None) -> int:
    """Calculate safe worker count based on CPU core count and current RAM pressure."""
    try:
        cpu_cores = os.cpu_count() or 4
        max_cpu_workers = base_workers or max(2, int(cpu_cores * 0.75))
        ram_load = get_system_ram_load()
        if ram_load > 88:
            return 1
        if ram_load > 75:
            return max(2, int(max_cpu_workers * 0.35))
        if ram_load >= 65:
            return max(2, int(max_cpu_workers * 0.65))
        return max_cpu_workers
    except Exception:
        return 2


class DynamicWorkerRegulator:
    """Adaptive resource regulator capping system RAM/CPU below 75% safety ceiling.

    Dynamically meters active concurrent workers without choking to a single thread.
    - Green Zone (< 65% RAM): 100% capacity (up to max_workers).
    - Yellow Zone (65% - 75% RAM): Soft-throttle to ~65% capacity.
    - Red Zone (> 75% RAM): Throttle to floor of 2 workers, force gc.collect(), pace tasks.
    - Emergency (> 88% RAM): Hard protection at 1 worker with gc.collect().
    - Hysteresis: Recovers back to higher tiers only after RAM drops below 60% across 2 checks.
    """
    def __init__(self, get_ram_fn, base_workers=None):
        self.get_ram_fn = get_ram_fn
        cpu_cores = os.cpu_count() or 4
        self.max_workers = base_workers or max(2, int(cpu_cores * 0.75))
        self.current_allowed = self.max_workers
        self.low_ram_streak = 0
        self.active_count = 0
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.last_check_time = 0.0
        self.cached_ram = 50

    def sample_ram(self, force=False):
        now = time.time()
        if force or (now - self.last_check_time) >= 0.8:
            try:
                self.cached_ram = self.get_ram_fn()
            except Exception:
                self.cached_ram = 50
            self.last_check_time = now
        return self.cached_ram

    def update_limits(self):
        ram = self.sample_ram()
        with self.cv:
            if ram > 88:
                self.current_allowed = 1
                self.low_ram_streak = 0
                try:
                    gc.collect()
                except Exception:
                    pass
            elif ram > 75:
                # Cap 75% reached: soft throttle to at least 2 workers
                self.current_allowed = max(2, int(self.max_workers * 0.35))
                self.low_ram_streak = 0
                try:
                    gc.collect()
                except Exception:
                    pass
            elif ram >= 65:
                # Warning zone: 65% - 75%
                self.current_allowed = max(2, int(self.max_workers * 0.65))
                self.low_ram_streak = 0
            else:
                # Normal zone: < 65%
                if ram < 60:
                    self.low_ram_streak += 1
                if self.low_ram_streak >= 2 or self.current_allowed == self.max_workers:
                    self.current_allowed = self.max_workers
            self.cv.notify_all()

    def acquire(self, abort_check=None):
        with self.cv:
            while True:
                if abort_check and abort_check():
                    return False
                self.update_limits()
                if self.active_count < self.current_allowed:
                    self.active_count += 1
                    if self.cached_ram > 75:
                        time.sleep(0.15)
                    return True
                self.cv.wait(timeout=0.3)

    def release(self):
        with self.cv:
            self.active_count = max(0, self.active_count - 1)
            self.cv.notify_all()
