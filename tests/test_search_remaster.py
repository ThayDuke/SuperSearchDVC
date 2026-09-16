import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import Api
from index_store import IndexStore


def entry(scan_id, path, title, content, year="2025"):
    clean = content.lower().replace("đ", "d")
    return {
        "scan_id": scan_id,
        "path": path,
        "title": title,
        "title_clean": title.lower().replace("đ", "d"),
        "original_path": path,
        "absolute_original_path": path,
        "domain": "IT",
        "doc_type": "Tài liệu nghiệp vụ / Báo cáo",
        "language": "Tiếng Việt (VN)",
        "year": year,
        "file_year": int(year) if str(year).isdigit() else 0,
        "file_month": 1,
        "source_type": "formal_document",
        "ocr_quality_score": 1.0,
        "wordCount": len(content.split()),
        "content": content,
        "content_clean": clean,
        "source_size": len(content),
        "source_mtime_ns": 1,
        "source_sha256": None,
    }


class SearchRemasterTests(unittest.TestCase):
    def make_store(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return IndexStore(os.path.join(temp_dir.name, "search.db"))

    def test_stopword_is_retained_and_phrase_wins(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "exact.txt", "Exact", "và khả năng xử lý hồ sơ"),
            entry("s", "separate.txt", "Separate", "và quy trình có nhiều bước trước khả năng xử lý"),
            entry("s", "only.txt", "Only", "khả năng xử lý hồ sơ"),
        ])

        result = store.search_documents("và khả năng", 1, 10)

        self.assertEqual(result["query_tokens"], ["va", "kha", "nang"])
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["documents"][0]["title"], "Exact")
        self.assertIn("và", result["documents"][0]["snippet"])
        self.assertIn("khả năng", result["documents"][0]["snippet"])

    def test_negation_token_is_not_removed(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "negative.txt", "Negative", "không khả năng tiếp tục xử lý"),
            entry("s", "positive.txt", "Positive", "khả năng tiếp tục xử lý"),
        ])

        result = store.search_documents("không khả năng", 1, 10)

        self.assertEqual(result["query_tokens"], ["khong", "kha", "nang"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["documents"][0]["title"], "Negative")

    def test_reserved_fts_words_are_literal(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "literal.txt", "Literal", "AND OR NOT literal"),
        ])

        result = store.search_documents("AND OR NOT", 1, 10)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["documents"][0]["title"], "Literal")

    def test_diacritic_and_d_letter_normalization(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "condition.txt", "Điều kiện", "điều kiện kiểm soát"),
        ])

        accented = store.search_documents("điều kiện", 1, 10)
        unaccented = store.search_documents("dieu kien", 1, 10)

        self.assertEqual(accented["total"], 1)
        self.assertEqual(unaccented["total"], 1)
        self.assertEqual(accented["documents"][0]["document_id"], unaccented["documents"][0]["document_id"])

    def test_spelling_suggestion_uses_body_vocabulary(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "sports.txt", "Sports guide", "The rules of football"),
        ])

        exact = store.search_documents("football")
        typo = store.search_documents("footbal")

        self.assertEqual(exact["total"], 1)
        self.assertIsNone(exact["suggested_query"])
        self.assertEqual(typo["total"], 0)
        self.assertEqual(typo["suggested_query"], "football")
        self.assertEqual(typo["suggestion_reason"], "spelling")

    def test_spelling_suggestion_preserves_correct_query_tokens(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "sports.txt", "Sports guide", "football safety rules"),
        ])

        typo = store.search_documents("footbal saftey")

        self.assertEqual(typo["suggested_query"], "football safety")

    def test_within_query_is_separate_from_phrase_ranking(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "contract.txt", "Contract", "và khả năng xử lý hợp đồng"),
            entry("s", "policy.txt", "Policy", "và khả năng xử lý chính sách"),
        ])

        result = store.search_documents(
            "và khả năng", 1, 10, {"within_query": "hợp đồng"}
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["documents"][0]["title"], "Contract")

    def test_snippet_is_plain_text_and_preserves_accents(self):
        store = self.make_store()
        store.replace_entries([
            entry("s", "accent.txt", "Accent", "Tài liệu về và khả năng kiểm soát."),
        ])

        result = store.search_documents("và khả năng", 1, 10)

        snippet = result["documents"][0]["snippet"]
        self.assertIn("Tài liệu", snippet)
        self.assertIn("khả năng", snippet)
        self.assertNotIn("<mark", snippet)

    def test_old_index_reports_reindex_requirement(self):
        store = self.make_store()
        store.replace_entries([entry("s", "one.txt", "One", "nội dung")])
        with store._connection() as connection:
            connection.execute("DELETE FROM index_metadata WHERE key = 'semantics_version'")

        self.assertTrue(store.stats()["requires_reindex"])
        self.assertTrue(store.search_documents("nội dung")["requires_reindex"])

    def test_creation_time_ignores_filename_content_and_mtime(self):
        api = Api.__new__(Api)
        stat_result = SimpleNamespace(
            st_birthtime=1735689600,
            st_mtime=1893456000,
        )
        with patch("app.os.stat", return_value=stat_result):
            year, month = api._get_file_creation_parts("report_2099_1920x1080.txt")

        self.assertEqual((year, month), (2025, 1))

    def test_missing_creation_time_does_not_fallback_to_mtime(self):
        api = Api.__new__(Api)
        stat_result = SimpleNamespace(st_mtime=1893456000)
        with patch("app.os.stat", return_value=stat_result):
            year, month = api._get_file_creation_parts("legacy.txt")

        self.assertEqual((year, month), (0, 0))

    def test_api_export_and_capabilities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            api = Api.__new__(Api)
            api.base_dir = temp_dir
            api.index_store = MagicMock()
            api.index_store.get_document.return_value = {
                "title": "Football guide",
                "original_path": "C:/docs/football.pdf",
                "doc_type": "Tài liệu",
                "year": "2025",
                "content": "# Football\n\nA short guide.",
            }

            capabilities = api.get_runtime_capabilities()
            self.assertTrue(capabilities["export_document"])
            self.assertTrue(capabilities["open_document_location"])
            markdown = api.export_document("doc-1", "md", temp_dir)
            docx = api.export_document("doc-1", "docx", temp_dir)
            self.assertTrue(markdown["success"])
            self.assertTrue(docx["success"])
            self.assertTrue(os.path.isfile(markdown["path"]))
            self.assertTrue(os.path.isfile(docx["path"]))

    def test_api_open_document_location_uses_document_id(self):
        api = Api.__new__(Api)
        api.index_store = MagicMock()
        api.index_store.get_document.return_value = {
            "absolute_original_path": r"\\?\C:\Documents\Football Guide.pdf",
        }
        api.index_store.resolve_file_path.return_value = r"\\?\C:\Documents\Football Guide.pdf"
        with patch("app.os.path.isfile", return_value=True), patch("subprocess.Popen") as popen:
            result = api.open_document_location("doc-1")

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "selected_file")
        self.assertEqual(result["path"], r"C:\Documents\Football Guide.pdf")
        popen.assert_called_once_with(["explorer.exe", "/select,", r"C:\Documents\Football Guide.pdf"])

    def test_api_open_document_location_prefers_current_scan_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scan_dir = os.path.join(temp_dir, "scanned")
            os.makedirs(scan_dir)
            source = os.path.join(scan_dir, "football.pdf")
            with open(source, "wb") as handle:
                handle.write(b"source")

            api = Api.__new__(Api)
            api.scan_dir = scan_dir
            api.index_store = MagicMock()
            api.index_store.get_document.return_value = {
                "original_path": "football.pdf",
                "absolute_original_path": os.path.join(temp_dir, "Documents", "football.pdf"),
            }
            with patch("subprocess.Popen") as popen:
                result = api.open_document_location("doc-1")

            self.assertTrue(result["success"])
            self.assertEqual(result["path"], source)
            popen.assert_called_once_with(["explorer.exe", "/select,", source])

    def test_api_open_explorer_resolves_legacy_relative_path_in_scan_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "football.pdf")
            with open(source, "wb") as handle:
                handle.write(b"source")
            api = Api.__new__(Api)
            api.scan_dir = temp_dir
            api.index_store = MagicMock()
            api.index_store.resolve_file_path.return_value = None
            with patch("subprocess.Popen") as popen:
                result = api.open_explorer("football.pdf")
            self.assertTrue(result)
            popen.assert_called_once_with(["explorer.exe", "/select,", source])

    def test_api_open_explorer_keeps_comma_filename_as_separate_argument(self):
        api = Api.__new__(Api)
        api.scan_dir = None
        api.index_store = MagicMock()
        api.index_store.resolve_file_path.return_value = None
        path = r"C:\Books\Global Success, tập một.pdf"
        with patch("app.os.path.isfile", return_value=True), patch("subprocess.Popen") as popen:
            result = api.open_explorer(path)
        self.assertTrue(result)
        popen.assert_called_once_with(["explorer.exe", "/select,", path])

    def test_html_export_success_dialog_has_full_path_and_navigation(self):
        with open(os.path.join(REPO_ROOT, "data", "SuperSearch.html"), "r", encoding="utf-8") as handle:
            html = handle.read()
        self.assertIn('id="lgAlertActions"', html)
        self.assertIn('showExportSuccessDialog(res, format)', html)
        self.assertIn('format === "docx" ? "Đến file docx" : "Đến file markdown"', html)
        self.assertIn('path.textContent = String(result && result.path || "")', html)

    def test_sync_entries_incremental_and_delete(self):
        store = self.make_store()
        doc1 = entry("scan1", "file1.txt", "Tài liệu 1", "nội dung tìm kiếm ban đầu", year="2025")
        doc1["source_mtime_ns"] = 100
        doc2 = entry("scan1", "file2.txt", "Tài liệu 2", "thông tin độc lập khác", year="2025")
        doc2["source_mtime_ns"] = 200

        # Bước 1: Đồng bộ lần đầu (2 documents)
        store.sync_entries([doc1, doc2], scan_id="scan1")
        self.assertEqual(store.count_documents(), 2)
        self.assertEqual(store.search_documents("ban đầu")["total"], 1)

        # Bước 2: Sửa doc1, giữ nguyên doc2
        doc1_updated = entry("scan1", "file1.txt", "Tài liệu 1", "nội dung đã được cập nhật mới", year="2025")
        doc1_updated["source_mtime_ns"] = 150
        store.sync_entries([doc1_updated, doc2], scan_id="scan1")
        self.assertEqual(store.count_documents(), 2)
        self.assertEqual(store.search_documents("ban đầu")["total"], 0)
        self.assertEqual(store.search_documents("cập nhật mới")["total"], 1)

        # Bước 3: Xóa doc2 (chỉ gửi doc1_updated)
        store.sync_entries([doc1_updated], scan_id="scan1")
        self.assertEqual(store.count_documents(), 1)
        self.assertEqual(store.search_documents("độc lập")["total"], 0)
        self.assertEqual(store.search_documents("cập nhật mới")["total"], 1)


if __name__ == "__main__":
    unittest.main()
