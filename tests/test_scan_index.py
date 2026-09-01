import os
import json
import sys
import tempfile
import unittest
import zipfile


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import Api


class ScanIndexRegressionTests(unittest.TestCase):
    def test_local_core_text_feed_notebook_and_zip_formats_are_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = os.path.join(temp_dir, "app")
            source_dir = os.path.join(temp_dir, "documents")
            os.makedirs(source_dir)
            repeated = "Nội dung kiểm thử SuperSearch hỗ trợ tìm kiếm tài liệu nội bộ. " * 4
            fixtures = {
                "notes.txt": repeated + "Mã định dạng TXT.",
                "memo.text": repeated + "Mã định dạng TEXT.",
                "guide.markdown": "# Hướng dẫn Markdown\n\n" + repeated,
                "data.json": json.dumps({"marker": "JSON nội bộ", "content": repeated}, ensure_ascii=False),
                "events.jsonl": json.dumps({"marker": "JSONL nội bộ", "content": repeated}, ensure_ascii=False),
                "table.csv": "Tên,Nội dung\nCSV nội bộ," + repeated,
                "config.xml": "<?xml version=\"1.0\"?><root><name>XML nội bộ</name><content>" + repeated + "</content></root>",
                "feed.rss": "<?xml version=\"1.0\"?><rss version=\"2.0\"><channel><title>RSS nội bộ</title><item><title>Bản tin</title><description>" + repeated + "</description></item></channel></rss>",
                "feed.atom": "<?xml version=\"1.0\"?><feed xmlns=\"http://www.w3.org/2005/Atom\"><title>Atom nội bộ</title><entry><title>Bản tin Atom</title><summary>" + repeated + "</summary></entry></feed>",
            }
            for name, content in fixtures.items():
                with open(os.path.join(source_dir, name), "w", encoding="utf-8") as handle:
                    handle.write(content)

            notebook = {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"title": "Notebook nội bộ"},
                "cells": [
                    {"cell_type": "markdown", "metadata": {}, "source": ["# Notebook nội bộ\n", repeated]},
                    {"cell_type": "code", "metadata": {}, "source": ["notebook_marker = 'searchable'"], "outputs": [], "execution_count": None},
                ],
            }
            with open(os.path.join(source_dir, "analysis.ipynb"), "w", encoding="utf-8") as handle:
                json.dump(notebook, handle, ensure_ascii=False)
            with zipfile.ZipFile(os.path.join(source_dir, "bundle.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("inside.txt", repeated + "ZIP nội bộ searchable_archive_marker.")
            with zipfile.ZipFile(os.path.join(source_dir, "book.epub"), "w", zipfile.ZIP_DEFLATED) as epub:
                epub.writestr("mimetype", "application/epub+zip")
                epub.writestr(
                    "META-INF/container.xml",
                    "<?xml version=\"1.0\"?><container><rootfiles><rootfile full-path=\"OEBPS/content.opf\"/></rootfiles></container>",
                )
                epub.writestr(
                    "OEBPS/content.opf",
                    "<?xml version=\"1.0\"?><package xmlns:dc=\"http://purl.org/dc/elements/1.1/\"><metadata><dc:title>EPUB nội bộ</dc:title></metadata><manifest><item id=\"chapter\" href=\"chapter.xhtml\"/></manifest><spine><itemref idref=\"chapter\"/></spine></package>",
                )
                epub.writestr(
                    "OEBPS/chapter.xhtml",
                    "<html><body><h1>EPUB nội bộ</h1><p>" + repeated + " epub_search_marker</p></body></html>",
                )

            api = Api(app_dir)
            api.scan_dir = source_dir
            result = api.scan_and_index()

            self.assertTrue(result["success"], result)
            self.assertEqual(result["error_count"], 0, result)
            self.assertEqual(result["total_entries"], 12)
            self.assertEqual(api.search_documents("searchable_archive_marker", 1, 10)["total"], 1)
            self.assertEqual(api.search_documents("notebook_marker", 1, 10)["total"], 1)
            self.assertEqual(api.search_documents("epub_search_marker", 1, 10)["total"], 1)
            extensions = api.get_index_stats()["extensions"]
            for extension in ("TXT", "TEXT", "MARKDOWN", "JSON", "JSONL", "CSV", "XML", "RSS", "ATOM", "IPYNB", "ZIP", "EPUB"):
                self.assertEqual(extensions.get(extension), 1, extensions)

    def test_unsafe_zip_is_rejected_without_losing_valid_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = os.path.join(temp_dir, "app")
            source_dir = os.path.join(temp_dir, "documents")
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, "valid.txt"), "w", encoding="utf-8") as handle:
                handle.write("Tài liệu hợp lệ cần được giữ lại trong chỉ mục. " * 6)

            api = Api(app_dir)
            api.scan_dir = source_dir
            first_result = api.scan_and_index()
            self.assertTrue(first_result["success"], first_result)

            with zipfile.ZipFile(os.path.join(source_dir, "unsafe.zip"), "w") as archive:
                archive.writestr("../escape.txt", "Nội dung không được phép index. " * 4)
            second_result = api.scan_and_index()

            self.assertTrue(second_result["success"], second_result)
            self.assertEqual(second_result["total_entries"], 1)
            self.assertEqual(second_result["error_summary"], {"unsafe_archive": 1})
            self.assertEqual(api.get_index_stats()["total"], 1)

    def test_capability_report_keeps_network_and_cloud_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = Api(temp_dir).get_supported_formats()
            self.assertEqual(report["profile"], "LOCAL_CORE")
            self.assertEqual(report["markitdown_version"], "0.1.7")
            self.assertEqual(len(report["enabled_extensions"]), 28)
            self.assertFalse(report["optional_profiles"]["network"]["enabled"])
            self.assertFalse(report["optional_profiles"]["cloud"]["enabled"])

    def test_html_and_htm_visible_content_is_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = os.path.join(temp_dir, "build_artifacts")
            source_dir = os.path.join(temp_dir, "documents")
            os.makedirs(source_dir)
            html = (
                "<!doctype html><html><head><title>HTML kiểm thử</title>"
                "<style>.hidden { display: none; }</style>"
                "<script>const script_secret_marker = 'hidden';</script></head>"
                "<body><h1>Tài liệu HTML nội bộ</h1>"
                "<p>Nội dung hiển thị dùng để tìm kiếm trong hồ sơ.</p>"
                "<ul><li>Quy trình vận hành</li><li>Kiểm soát truy cập</li></ul>"
                "<table><tr><td>Phòng ban</td><td>IT</td></tr></table></body></html>"
            )
            for extension in ("html", "htm"):
                with open(os.path.join(source_dir, f"example.{extension}"), "w", encoding="utf-8") as handle:
                    handle.write(html)

            api = Api(app_dir)
            api.scan_dir = source_dir
            result = api.scan_and_index()

            self.assertTrue(result["success"], result)
            self.assertEqual(result["total_entries"], 2)
            stats = api.get_index_stats()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["extensions"], {"HTML": 1, "HTM": 1})
            self.assertEqual(api.search_documents("nội bộ", 1, 10)["total"], 2)
            self.assertEqual(api.search_documents("script_secret_marker", 1, 10)["total"], 0)

    def test_runtime_under_build_artifacts_is_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = os.path.join(temp_dir, "build_artifacts")
            source_dir = os.path.join(temp_dir, "documents")
            os.makedirs(source_dir)
            source_path = os.path.join(source_dir, "example.md")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write("# Tài liệu kiểm thử\n\n" + "Nội dung tìm kiếm hợp lệ. " * 12)

            api = Api(app_dir)
            api.scan_dir = source_dir
            result = api.scan_and_index()

            self.assertTrue(result["success"], result)
            self.assertEqual(result["total_entries"], 1)
            self.assertEqual(api.get_index_stats()["total"], 1)

    def test_empty_reindex_keeps_previous_sqlite_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = os.path.join(temp_dir, "build_artifacts")
            source_dir = os.path.join(temp_dir, "documents")
            os.makedirs(source_dir)
            source_path = os.path.join(source_dir, "example.md")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write("# Tài liệu kiểm thử\n\n" + "Nội dung tìm kiếm hợp lệ. " * 12)

            api = Api(app_dir)
            api.scan_dir = source_dir
            first_result = api.scan_and_index()
            self.assertTrue(first_result["success"], first_result)

            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write("rỗng")
            second_result = api.scan_and_index()

            self.assertFalse(second_result["success"])
            self.assertEqual(api.get_index_stats()["total"], 1)


if __name__ == "__main__":
    unittest.main()
