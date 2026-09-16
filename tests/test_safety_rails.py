import io
import os
import sys
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import (
    Api,
    safe_long_path,
    open_file_with_retry,
    run_with_timeout,
    SafeZipConverter,
)
from index_store import IndexStore


class SafetyRailsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_long_path_formatting(self):
        """Test tiền tố đường dẫn dài Windows \\?\\."""
        short_path = "C:\\short\\path\\doc.pdf"
        self.assertEqual(safe_long_path(short_path), os.path.normpath(short_path))

        long_component = "a" * 250
        long_path = f"C:\\folder\\{long_component}\\doc.pdf"
        res = safe_long_path(long_path)
        if sys.platform.startswith("win"):
            self.assertTrue(res.startswith("\\\\?\\"))
            self.assertIn(long_component, res)

    def test_run_with_timeout_success(self):
        """Test run_with_timeout hoàn thành bình thường trong giới hạn thời gian."""
        def quick_task(x, y):
            return x + y

        result = run_with_timeout(quick_task, args=(10, 20), timeout=2)
        self.assertEqual(result, 30)

    def test_run_with_timeout_exceeded(self):
        """Test run_with_timeout ném TimeoutError khi tác vụ bị treo/chạy quá lâu."""
        def hanging_task():
            time.sleep(1.5)
            return "done"

        with self.assertRaises(TimeoutError):
            run_with_timeout(hanging_task, timeout=0.3)

    def test_pdf_conversion_uses_cooperative_execution_without_hard_timeout(self):
        with patch("app.run_with_timeout") as timeout_runner:
            result = Api._run_conversion_with_timeout_policy(lambda: "pdf-result", ".pdf")

        self.assertEqual(result, "pdf-result")
        timeout_runner.assert_not_called()

    def test_non_pdf_conversion_keeps_hard_timeout(self):
        with patch("app.run_with_timeout", return_value="docx-result") as timeout_runner:
            result = Api._run_conversion_with_timeout_policy(lambda: "ignored", ".docx")

        self.assertEqual(result, "docx-result")
        timeout_runner.assert_called_once()
        self.assertEqual(timeout_runner.call_args.kwargs["timeout"], 60)

    def test_pdf_scan_workers_are_capped(self):
        api = Api(self.temp_dir.name)
        api.get_safe_workers_count = lambda: 9

        self.assertEqual(api._scan_worker_count([{"src_path": "book.pdf"}]), 2)
        self.assertEqual(api._scan_worker_count([{"src_path": "notes.docx"}]), 9)

    def test_open_file_with_retry(self):
        """Test mở tệp với cơ chế retry an toàn."""
        test_file = os.path.join(self.temp_dir.name, "retry_test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("content to test retry")

        with open_file_with_retry(test_file, "r") as f:
            data = f.read()
        self.assertEqual(data, "content to test retry")

    def test_zip_filename_decoding_cp437_fallback(self):
        """Test giải mã tên tệp tiếng Việt trong ZIP khi không có cờ UTF-8."""
        raw_name = "Báo cáo tiến độ.txt"
        cp437_encoded = raw_name.encode("utf-8").decode("cp437", errors="replace")

        info = zipfile.ZipInfo(cp437_encoded)
        info.flag_bits = 0  # Cờ UTF-8 (0x800) không bật
        decoded = SafeZipConverter._decode_filename(info)
        self.assertIn("Báo cáo", decoded)

    def test_cleanup_stale_temp_files(self):
        """Test dọn dẹp các tệp tạm .tmp-* mồ côi khi khởi động."""
        api = Api(self.temp_dir.name)
        # Tạo 1 file .tmp cũ (> 65s)
        stale_tmp = os.path.join(api.runtime_dir, "test.tmp-99999")
        with open(stale_tmp, "w", encoding="utf-8") as f:
            f.write("stale temp data")
        past_time = time.time() - 100
        os.utime(stale_tmp, (past_time, past_time))

        # Chạy cleanup
        api._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(stale_tmp))

    def test_sqlite_pragmas_tuning(self):
        """Test các Pragmas hiệu năng cao đã được kích hoạt trong IndexStore."""
        db_path = os.path.join(self.temp_dir.name, "test_pragmas.db")
        store = IndexStore(db_path)
        with store._connection() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            sync_mode = conn.execute("PRAGMA synchronous").fetchone()[0]
            temp_store = conn.execute("PRAGMA temp_store").fetchone()[0]

            self.assertEqual(journal_mode.lower(), "wal")
            # 1 tương ứng với NORMAL
            self.assertEqual(sync_mode, 1)
            # 2 tương ứng với MEMORY
            self.assertEqual(temp_store, 2)


if __name__ == "__main__":
    unittest.main()
