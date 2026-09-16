"""Folder Watchdog for SuperSearch.

Monitors target folders for file additions, modifications, and deletions
in real-time on Windows using native ReadDirectoryChangesW (ctypes) with
an adaptive debounce buffer to prevent file lock conflicts.
Zero external dependencies (Python standard library only).
"""

import os
import sys
import time
import ctypes
import threading
from typing import Callable, Set, Dict

# Supported extensions to watch
WATCHED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".txt", ".md", ".html", ".htm", ".csv",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
}

# Windows API Constants
FILE_LIST_DIRECTORY = 0x0001
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_SIZE = 0x00000008

FILE_ACTION_ADDED = 1
FILE_ACTION_REMOVED = 2
FILE_ACTION_MODIFIED = 3
FILE_ACTION_RENAMED_OLD_NAME = 4
FILE_ACTION_RENAMED_NEW_NAME = 5


class FILE_NOTIFY_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", ctypes.c_uint32),
        ("Action", ctypes.c_uint32),
        ("FileNameLength", ctypes.c_uint32),
        ("FileName", ctypes.c_wchar * 1),
    ]


class FolderWatchdog:
    """Monitors directory changes on Windows with debounce and file-lock protection."""

    def __init__(self, debounce_seconds: float = 2.5):
        self.debounce_seconds = debounce_seconds
        self.watch_folder = None
        self.on_change_callback = None
        self.on_overflow_callback = None
        self._stop_event = threading.Event()
        self._thread = None
        self._debounce_thread = None
        self._pending_changes: Dict[str, float] = {}
        self._pending_deletions: Set[str] = set()
        self._lock = threading.Lock()
        self._dir_handle = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        folder_path: str,
        on_change_callback: Callable[[Set[str], Set[str]], None],
        on_overflow_callback: Callable[[], None] = None,
    ):
        """Starts monitoring the specified directory."""
        if not os.path.isdir(folder_path):
            raise ValueError(f"Thư mục không tồn tại: {folder_path}")

        self.stop()
        self.watch_folder = os.path.abspath(folder_path)
        self.on_change_callback = on_change_callback
        self.on_overflow_callback = on_overflow_callback
        self._stop_event.clear()

        # Start debounce flusher thread
        self._debounce_thread = threading.Thread(target=self._debounce_flusher, daemon=True)
        self._debounce_thread.start()

        # Start directory watcher thread
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the watchdog threads."""
        self._stop_event.set()
        if self._dir_handle and self._dir_handle != INVALID_HANDLE_VALUE:
            try:
                ctypes.windll.kernel32.CancelIoEx(self._dir_handle, None)
            except Exception:
                pass
            try:
                ctypes.windll.kernel32.CloseHandle(self._dir_handle)
            except Exception:
                pass
            self._dir_handle = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        if self._debounce_thread and self._debounce_thread.is_alive():
            self._debounce_thread.join(timeout=1.0)

        with self._lock:
            self._pending_changes.clear()
            self._pending_deletions.clear()

    def _is_watched(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext in WATCHED_EXTENSIONS:
            # Ignore temporary files
            base = os.path.basename(path)
            if base.startswith("~$") or base.startswith(".~") or ".tmp" in base:
                return False
            return True
        return False

    def _is_file_accessible(self, path: str) -> bool:
        """Returns True if file is fully written and accessible for shared read."""
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "rb") as f:
                f.read(1)
            return True
        except (PermissionError, OSError):
            return False

    def _queue_change(self, full_path: str, action: int):
        if not self._is_watched(full_path):
            return

        with self._lock:
            if action == FILE_ACTION_REMOVED or action == FILE_ACTION_RENAMED_OLD_NAME:
                self._pending_deletions.add(full_path)
                self._pending_changes.pop(full_path, None)
            else:
                self._pending_changes[full_path] = time.time()
                self._pending_deletions.discard(full_path)

    def _debounce_flusher(self):
        """Periodically flushes debounced changes to the callback."""
        while not self._stop_event.is_set():
            time.sleep(0.5)
            now = time.time()
            to_process_changes = set()
            to_process_deletions = set()

            with self._lock:
                # Find ready changes (no events for debounce_seconds)
                for path, last_time in list(self._pending_changes.items()):
                    if now - last_time >= self.debounce_seconds:
                        if self._is_file_accessible(path):
                            to_process_changes.add(path)
                            del self._pending_changes[path]
                        elif not os.path.exists(path):
                            to_process_deletions.add(path)
                            del self._pending_changes[path]

                # Deletions can be processed immediately after debounce
                if self._pending_deletions:
                    to_process_deletions.update(self._pending_deletions)
                    self._pending_deletions.clear()

            if (to_process_changes or to_process_deletions) and self.on_change_callback:
                try:
                    self.on_change_callback(to_process_changes, to_process_deletions)
                except Exception as exc:
                    print(f"[FolderWatchdog] Callback error: {exc}")

    def _watch_loop(self):
        """Native Windows ReadDirectoryChangesW loop."""
        if not sys.platform.startswith("win"):
            self._fallback_polling_loop()
            return

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            self.watch_folder,
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

        if handle == INVALID_HANDLE_VALUE:
            print("[FolderWatchdog] CreateFileW failed, fallback to polling.")
            self._fallback_polling_loop()
            return

        self._dir_handle = handle
        buffer_size = 65536
        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_returned = ctypes.c_ulong(0)

        notify_filter = (
            FILE_NOTIFY_CHANGE_FILE_NAME
            | FILE_NOTIFY_CHANGE_DIR_NAME
            | FILE_NOTIFY_CHANGE_LAST_WRITE
            | FILE_NOTIFY_CHANGE_SIZE
        )

        try:
            while not self._stop_event.is_set():
                success = kernel32.ReadDirectoryChangesW(
                    self._dir_handle,
                    ctypes.byref(buffer),
                    buffer_size,
                    True,  # watch subtree (recursive)
                    notify_filter,
                    ctypes.byref(bytes_returned),
                    None,
                    None,
                )

                if not success or bytes_returned.value == 0:
                    if self._stop_event.is_set():
                        break
                    err = kernel32.GetLastError()
                    if err == 1002:  # ERROR_NOTIFY_ENUM_DIR: buffer overflow
                        print("[FolderWatchdog] Buffer overflow (1002). Triggering recovery.")
                        if self.on_overflow_callback:
                            try:
                                self.on_overflow_callback()
                            except Exception as ex:
                                print(f"[FolderWatchdog] Overflow callback error: {ex}")
                    time.sleep(0.2)
                    continue

                offset = 0
                while True:
                    info = FILE_NOTIFY_INFORMATION.from_buffer(buffer, offset)
                    file_name_length = info.FileNameLength // 2
                    file_name_buffer = (ctypes.c_wchar * file_name_length).from_buffer(
                        buffer, offset + 12
                    )
                    relative_path = file_name_buffer[:file_name_length]
                    full_path = os.path.join(self.watch_folder, relative_path)
                    action = info.Action

                    self._queue_change(full_path, action)

                    if info.NextEntryOffset == 0:
                        break
                    offset += info.NextEntryOffset
        except Exception as exc:
            if not self._stop_event.is_set():
                print(f"[FolderWatchdog] Error in watch loop: {exc}")
        finally:
            if self._dir_handle and self._dir_handle != INVALID_HANDLE_VALUE:
                try:
                    kernel32.CloseHandle(self._dir_handle)
                except Exception:
                    pass
                self._dir_handle = None

    def _fallback_polling_loop(self):
        """Lightweight mtime/size polling for non-Windows or fallback scenarios."""
        known_files = {}
        while not self._stop_event.is_set():
            time.sleep(3.0)
            if not self.watch_folder or not os.path.isdir(self.watch_folder):
                continue

            current_files = {}
            for root, _, files in os.walk(self.watch_folder):
                for f in files:
                    full_p = os.path.join(root, f)
                    if self._is_watched(full_p):
                        try:
                            stat = os.stat(full_p)
                            current_files[full_p] = (stat.st_mtime_ns, stat.st_size)
                        except OSError:
                            pass

            for p, meta in current_files.items():
                if p not in known_files or known_files[p] != meta:
                    self._queue_change(p, FILE_ACTION_MODIFIED)

            for p in list(known_files.keys()):
                if p not in current_files:
                    self._queue_change(p, FILE_ACTION_REMOVED)

            known_files = current_files
