"""Comprehensive unit tests for Advanced SuperSearch Capabilities:
1. Safe Chunking & Quota Manager
2. KaTeX offline bundle
3. BM25 Multi-Tier Weighted Ranking (Title > Heading > Body)
4. Export Service (Markdown & DOCX)
5. Folder Watchdog
"""

import os
import sys
import time
import shutil
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from gemini_ocr_engine import (
    GeminiQuotaManager,
    GeminiQuotaExhaustedError,
)
from index_store import (
    IndexStore,
    extract_headings,
    normalize_search_text,
)
from html_builder import build_html_document
from export_service import export_to_markdown, export_to_docx, DOCX_AVAILABLE
from folder_watchdog import FolderWatchdog


class TestGeminiQuotaManager(unittest.TestCase):
    def test_pacing_and_slots(self):
        qm = GeminiQuotaManager(min_interval=0.05, max_retries=2, base_backoff=0.05)
        start = time.time()
        qm.wait_for_slot()
        qm.wait_for_slot()
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.04)

    def test_exhaustion_lockout(self):
        qm = GeminiQuotaManager(min_interval=0.01, max_retries=2, base_backoff=0.05)
        qm.record_exhaustion(cooldown_seconds=10.0)
        with self.assertRaises(GeminiQuotaExhaustedError):
            qm.wait_for_slot()
        qm.reset()
        qm.wait_for_slot()  # should not raise after reset


class TestKaTeXOfflineAssets(unittest.TestCase):
    def test_local_katex_files_exist(self):
        vendor_dir = os.path.join(ROOT_DIR, "data", "vendor", "katex")
        self.assertTrue(os.path.isfile(os.path.join(vendor_dir, "katex.min.js")))
        self.assertTrue(os.path.isfile(os.path.join(vendor_dir, "katex.min.css")))
        self.assertTrue(os.path.isfile(os.path.join(vendor_dir, "auto-render.min.js")))

    def test_html_builder_uses_katex(self):
        md = "# Tiêu đề toán\nCông thức: $E = mc^2$\n$$\\int_0^1 x dx = \\frac{1}{2}$$"
        html = build_html_document(md, title="Test KaTeX")
        self.assertIn("vendor/katex/katex.min.css", html)
        self.assertIn("vendor/katex/katex.min.js", html)
        self.assertIn("renderMathInElement", html)
        self.assertNotIn("MathJax", html)


class TestBM25HeadingsAndRanking(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_bm25.db")
        self.store = IndexStore(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_headings(self):
        content = (
            "# Chương Một: Giới thiệu\n"
            "Nội dung chương một ở đây.\n"
            "## Mục 1.1: Khái niệm cơ bản\n"
            "Điều 5: Quyền và nghĩa vụ\n"
            "Chi tiết điều 5."
        )
        headings = extract_headings(content)
        self.assertIn("Chương Một: Giới thiệu", headings)
        self.assertIn("Mục 1.1: Khái niệm cơ bản", headings)
        self.assertIn("Điều 5: Quyền và nghĩa vụ", headings)

    def test_ranking_precedence_title_heading_content(self):
        # 3 documents with the keyword 'quangninh':
        # Doc 1: keyword only in general body content
        # Doc 2: keyword in a heading (## Dự án tại quangninh)
        # Doc 3: keyword in title (Tài liệu quy hoạch quangninh)
        entries = [
            {
                "scan_id": "test_scan",
                "title": "Báo cáo tổng hợp số 01.pdf",
                "title_clean": "bao cao tong hop so 01.pdf",
                "path": "docs/doc1.pdf",
                "original_path": "docs/doc1.pdf",
                "absolute_original_path": "C:/fake/doc1.pdf",
                "content": "Báo cáo thường niên năm 2026. Một số hoạt động diễn ra tại tỉnh quangninh.",
                "content_clean": "bao cao thuong nien nam 2026. mot so hoat dong dien ra tai tinh quangninh.",
            },
            {
                "scan_id": "test_scan",
                "title": "Phương án kỹ thuật bến cảng.docx",
                "title_clean": "phuong an ky thuat ben cang.docx",
                "path": "docs/doc2.docx",
                "original_path": "docs/doc2.docx",
                "absolute_original_path": "C:/fake/doc2.docx",
                "content": "# Phần 1: Giới thiệu\n## Dự án tại quangninh trọng điểm\nNội dung dự án.",
                "content_clean": "# phan 1: gioi thieu\n## du an tai quangninh trong diem\nnoi dung du an.",
            },
            {
                "scan_id": "test_scan",
                "title": "Quy hoạch hạ tầng quangninh 2026.pdf",
                "title_clean": "quy hoach ha tang quangninh 2026.pdf",
                "path": "docs/doc3.pdf",
                "original_path": "docs/doc3.pdf",
                "absolute_original_path": "C:/fake/doc3.pdf",
                "content": "Chi tiết các dự án hạ tầng lớn.",
                "content_clean": "chi tiet cac du an ha tang lon.",
            },
        ]

        self.store.replace_entries(entries)

        # Search for 'quangninh'
        res = self.store.search_documents("quangninh")
        docs = res["documents"]
        self.assertEqual(len(docs), 3)

        # Precedence check:
        # 1st rank: Doc 3 (Title match)
        # 2nd rank: Doc 2 (Heading match)
        # 3rd rank: Doc 1 (Body match only)
        self.assertEqual(docs[0]["title"], "Quy hoạch hạ tầng quangninh 2026.pdf")
        self.assertEqual(docs[1]["title"], "Phương án kỹ thuật bến cảng.docx")
        self.assertEqual(docs[2]["title"], "Báo cáo tổng hợp số 01.pdf")


class TestExportService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_to_markdown(self):
        doc = {
            "title": "Bản ghi nhớ hợp tác",
            "original_path": "C:/data/ghi_nho.pdf",
            "doc_type": "Văn bản",
            "year": "2026",
            "content": "# Điều khoản chung\nNội dung bản ghi nhớ.",
        }
        out_path = os.path.join(self.temp_dir, "exported.md")
        res_path = export_to_markdown(doc, out_path)
        self.assertTrue(os.path.isfile(res_path))
        with open(res_path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("title: \"Bản ghi nhớ hợp tác\"", text)
        self.assertIn("# Điều khoản chung", text)

    def test_export_to_docx(self):
        if not DOCX_AVAILABLE:
            self.skipTest("python-docx not installed")
        doc = {
            "title": "Đề án nghiên cứu",
            "original_path": "C:/data/de_an.docx",
            "doc_type": "Đề tài",
            "year": "2026",
            "content": (
                "# 1. Mở đầu\n"
                "Đây là đoạn văn có chữ **in đậm** và chữ *in nghiêng*.\n"
                "## 1.1. Bảng số liệu\n"
                "| STT | Tên chỉ tiêu | Giá trị |\n"
                "| --- | --- | --- |\n"
                "| 1 | Tốc độ | 100 ms |\n"
                "| 2 | Bộ nhớ | 120 MB |\n"
                "- Điểm quan trọng 1\n"
                "- Điểm quan trọng 2\n"
                "> Trích dẫn quan trọng\n"
            ),
        }
        out_path = os.path.join(self.temp_dir, "exported.docx")
        res_path = export_to_docx(doc, out_path)
        self.assertTrue(os.path.isfile(res_path))
        self.assertGreater(os.path.getsize(res_path), 5000)


class TestFolderWatchdog(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.watchdog = FolderWatchdog(debounce_seconds=0.3)

    def tearDown(self):
        self.watchdog.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_watchdog_filters_and_debounces(self):
        changed_detected = []
        def on_change(changed, deleted):
            changed_detected.extend(changed)

        self.watchdog.start(self.temp_dir, on_change)
        self.assertTrue(self.watchdog.is_running)

        # Create a valid watched file
        test_file = os.path.join(self.temp_dir, "document.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Hello Watchdog")

        # Create an ignored file (e.g. temp .tmp)
        tmp_file = os.path.join(self.temp_dir, "scratch.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("temporary")

        # Wait for debounce flusher
        time.sleep(1.2)
        self.watchdog.stop()

        self.assertIn(os.path.abspath(test_file), [os.path.abspath(p) for p in changed_detected])
        self.assertNotIn(os.path.abspath(tmp_file), [os.path.abspath(p) for p in changed_detected])


if __name__ == "__main__":
    unittest.main()
