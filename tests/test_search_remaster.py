import os
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
