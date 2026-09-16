import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import Api
from index_store import IndexStore, build_plain_snippet


def create_mock_entry(scan_id, rel_path, title, content):
    return {
        "scan_id": scan_id,
        "title": title,
        "title_clean": title.lower(),
        "headings_clean": "",
        "path": rel_path,
        "original_path": rel_path,
        "absolute_original_path": os.path.abspath(rel_path),
        "domain": "Chung",
        "doc_type": "Tài liệu",
        "language": "Tiếng Việt",
        "year": "2026",
        "file_year": 2026,
        "file_month": 9,
        "source_type": "formal_document",
        "ocr_quality_score": 1.0,
        "wordCount": len(content.split()),
        "source_size": len(content),
        "source_mtime_ns": 1000,
        "source_sha256": "dummyhash",
        "content": content,
        "content_clean": content.lower(),
    }


class AuditFixesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")
        self.store = IndexStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sync_entries_delete_missing_false_prevents_data_loss(self):
        """Test Lỗi 2: Watchdog sync 1 file không làm mất các file khác trong DB."""
        initial_entries = [
            create_mock_entry("scan1", f"doc{i}.txt", f"Tài liệu {i}", f"Nội dung văn bản số {i}")
            for i in range(1, 6)
        ]
        self.store.sync_entries(initial_entries, scan_id="scan1", delete_missing=True)
        self.assertEqual(self.store.count_documents(), 5)

        # Watchdog phát hiện 1 file doc1.txt thay đổi, sync_entries với delete_missing=False
        updated_doc1 = create_mock_entry("scan1", "doc1.txt", "Tài liệu 1 cập nhật", "Nội dung mới của tài liệu 1")
        self.store.sync_entries([updated_doc1], scan_id="scan1", delete_missing=False)

        # Toàn bộ 5 tài liệu vẫn phải còn nguyên trong cơ sở dữ liệu
        self.assertEqual(self.store.count_documents(), 5)
        res = self.store.search_documents("cập nhật")
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["documents"][0]["title"], "Tài liệu 1 cập nhật")

    def test_upsert_entries_helper(self):
        """Test upsert_entries tiện ích cho cập nhật từng phần."""
        entry1 = create_mock_entry("scanA", "file1.txt", "File 1", "Noi dung 1")
        entry2 = create_mock_entry("scanA", "file2.txt", "File 2", "Noi dung 2")
        self.store.sync_entries([entry1, entry2], scan_id="scanA")
        self.assertEqual(self.store.count_documents(), 2)

        # Upsert file 3
        entry3 = create_mock_entry("scanA", "file3.txt", "File 3", "Noi dung 3")
        self.store.upsert_entries([entry3], scan_id="scanA")
        self.assertEqual(self.store.count_documents(), 3)

    def test_delete_entries_by_paths(self):
        """Test Lỗi 3: Xóa tài liệu khỏi index theo đường dẫn khi Watchdog bắt sự kiện delete."""
        entries = [
            create_mock_entry("scanB", "folder/a.pdf", "File A", "Noi dung file A"),
            create_mock_entry("scanB", "folder/b.docx", "File B", "Noi dung file B"),
            create_mock_entry("scanB", "folder/c.xlsx", "File C", "Noi dung file C"),
        ]
        self.store.sync_entries(entries, scan_id="scanB")
        self.assertEqual(self.store.count_documents(), 3)

        # Xóa b.docx
        deleted = self.store.delete_entries_by_paths(["folder/b.docx"], scan_id="scanB")
        self.assertEqual(deleted, 1)
        self.assertEqual(self.store.count_documents(), 2)

        # Kiểm tra document folder/b.docx đã bị xóa hoàn toàn khỏi DB và không có trong kết quả tìm kiếm
        res_paths = [doc["relative_path"] for doc in self.store.search_documents("Noi dung")["documents"]]
        self.assertNotIn("folder/b.docx", res_paths)
        self.assertIn("folder/a.pdf", res_paths)
        self.assertIn("folder/c.xlsx", res_paths)

        # File A và File C vẫn tìm thấy
        res_a = self.store.search_documents("file A")
        self.assertEqual(res_a["total"], 1)

    def test_fts5_special_characters_no_crash(self):
        """Test Lỗi 4: Truy vấn FTS5 chứa ký tự đặc biệt không bị crash OperationalError."""
        entries = [
            create_mock_entry("scanC", "doc.txt", "Hướng dẫn sử dụng", "Nội dung quy trình công nghệ 2026"),
        ]
        self.store.sync_entries(entries, scan_id="scanC")

        problematic_queries = [
            'quy trình : 2026',
            'path: C:\\Users\\Desktop',
            '"chuỗi mở ngoặc kép không đóng',
            'AND OR NOT NEAR',
            'công nghệ *+^~',
            '((( ngoặc không cân bằng',
        ]
        for q in problematic_queries:
            try:
                res = self.store.search_documents(q)
                self.assertIsInstance(res, dict)
                self.assertIn("documents", res)
            except Exception as e:
                self.fail(f"Truy vấn '{q}' làm crash search_documents với lỗi: {e}")

    def test_api_convert_document_methods_exist(self):
        """Test Lỗi 1: Api class có các phương thức convert_file_to_markdown và _convert_document_to_markdown."""
        api = Api(self.temp_dir.name)
        self.assertTrue(hasattr(api, "convert_file_to_markdown"))
        self.assertTrue(hasattr(api, "_convert_document_to_markdown"))

        # Test chuyển đổi file txt mẫu
        sample_txt = os.path.join(self.temp_dir.name, "sample.txt")
        with open(sample_txt, "w", encoding="utf-8") as f:
            f.write("Hello SuperSearch offline conversion test")

        text = api.convert_file_to_markdown(sample_txt)
        self.assertIn("Hello SuperSearch offline conversion test", text)

        alias_text = api._convert_document_to_markdown(sample_txt)
        self.assertEqual(alias_text, text)

    def test_optimized_build_plain_snippet(self):
        """Test Tối ưu Snippet: Trích xuất nhanh và chính xác với tài liệu lớn."""
        # Tạo văn bản dài 120.000 ký tự
        padding_before = "Tài liệu lưu trữ nội bộ thông tin chung. " * 1500
        target_keyword = "TỪ KHÓA ĐẶC BIỆT CHÍNH XÁC"
        padding_after = "Phần nội dung kết thúc tài liệu quy chế. " * 1500
        full_content = padding_before + target_keyword + " " + padding_after

        snippet = build_plain_snippet(full_content, ["tu", "khoa", "dac", "biet"])
        self.assertIn("TỪ KHÓA ĐẶC BIỆT CHÍNH XÁC", snippet)
        self.assertTrue(len(snippet) <= 250)


if __name__ == "__main__":
    unittest.main()
