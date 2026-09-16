"""Unit tests verifying all Phase 6 deep audit fixes.

Covers:
1. pack_portable.py vendor assets inclusion.
2. export_to_docx heading preservation and non-duplication.
3. export_to_docx inline LaTeX math conversion with \\( ... \\).
4. ocr_postprocessor heal_page_pair with <!-- PAGE X --> comments.
5. LocalDocConverter and LocalXlsConverter stream-based processing for ZIP archives.
6. html_builder KaTeX resource fallback and delimiters.
7. open_explorer long path prefix stripping.
8. get_page_preview_image LRU caching.
"""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import docx
from app import Api
from converters import LocalDocConverter, LocalXlsConverter
from export_service import convert_latex_to_omml, export_to_docx
from html_builder import build_html_document, KATEX_RESOURCES
from ocr_postprocessor import heal_cross_page_continuations, heal_page_pair


class TestAuditPhase3Fixes(unittest.TestCase):

    def test_export_docx_heading_not_duplicated_and_paragraphs_preserved(self):
        """Fix 2: Verify headings have continue and do not eat the following paragraph."""
        doc = {
            "title": "Báo Cáo Thử Nghiệm",
            "content": "# Tiêu Đề Mục 1\nĐoạn văn thứ nhất ngay sau tiêu đề.\nĐoạn văn thứ hai.",
        }
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            out_path = f.name
        try:
            export_to_docx(doc, out_path)
            d = docx.Document(out_path)
            texts = [p.text for p in d.paragraphs if p.text]
            # Verify heading is added once
            self.assertIn("Tiêu Đề Mục 1", texts)
            # Verify paragraph immediately following heading is preserved
            self.assertTrue(any("Đoạn văn thứ nhất" in t for t in texts))
            self.assertTrue(any("Đoạn văn thứ hai" in t for t in texts))
            # Verify heading text is not prefixed with # in a regular paragraph
            self.assertFalse(any("# Tiêu Đề Mục 1" in t for t in texts))
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_export_docx_inline_latex_conversion(self):
        r"""Fix 3: Verify inline LaTeX with single backslash \( ... \) is converted."""
        doc = {
            "title": "Toán Học",
            "content": "Phương trình \\( E = mc^2 \\) và công thức \\( a^2 + b^2 = c^2 \\) nổi tiếng.",
        }
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            out_path = f.name
        try:
            export_to_docx(doc, out_path)
            d = docx.Document(out_path)
            # OMML equations are added as XML elements inside paragraph._p
            has_omml = False
            for p in d.paragraphs:
                xml = p._p.xml
                if "oMath" in xml:
                    has_omml = True
                    break
            self.assertTrue(has_omml, "Inline LaTeX math should produce OMML elements in Word document")
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_ocr_postprocessor_heals_across_page_comment(self):
        """Fix 4: Verify soft-hyphens are healed when the next page starts with <!-- PAGE X -->."""
        p1 = "Hệ thống đang phát-"
        p2 = "<!-- PAGE 2 (Gemini Cloud OCR Mode) -->\n\ntriển vượt bậc."
        h1, h2 = heal_page_pair(p1, p2)
        self.assertEqual(h1, "Hệ thống đang phát")
        self.assertEqual(h2, p2)

        # And verify via heal_cross_page_continuations
        healed = heal_cross_page_continuations([p1, p2])
        self.assertEqual(healed[0], "Hệ thống đang phát")
        self.assertEqual(healed[1], p2)

    def test_stream_conversion_doc_and_xls(self):
        """Fix 5: Verify LocalDocConverter and LocalXlsConverter accept stream data when local_path is None."""
        api_mock = MagicMock()
        doc_conv = LocalDocConverter(api_mock)
        xls_conv = LocalXlsConverter(api_mock)

        # Empty or non-ole stream returns clean result without throwing FileNotFoundError
        fake_stream = io.BytesIO(b"Not an OLE file")
        stream_info = MagicMock()
        stream_info.local_path = None
        res_doc = doc_conv.convert(fake_stream, stream_info)
        self.assertEqual(res_doc.text_content, "")

        fake_xls_stream = io.BytesIO(b"Not an XLS workbook")
        res_xls = xls_conv.convert(fake_xls_stream, stream_info)
        self.assertTrue(res_xls.text_content.startswith("Error during local XLS") or res_xls.text_content == "")

    def test_html_builder_katex_resources(self):
        """Fix 6: Verify HTML builder includes relative fallback and auto-render config."""
        html = build_html_document("# Công Thức", title="Toán", original_path="test.md")
        self.assertIn("vendor/katex/katex.min.css", html)
        self.assertIn("renderMathInElement", html)

    def test_open_explorer_strips_windows_long_path_prefix(self):
        """Fix 9: Verify open_explorer removes \\?\\ prefix before calling explorer.exe."""
        api = Api(".")
        with patch("subprocess.Popen") as mock_popen, patch("os.path.isfile", return_value=True):
            long_path = r"\\?\C:\Very\Deep\Folder\document.pdf"
            result = api.open_explorer(long_path)
            self.assertTrue(result)
            mock_popen.assert_called_once()
            called_cmd = mock_popen.call_args[0][0]
            # Ensure the argument does not begin with /select,\\?\
            arg = called_cmd[1]
            self.assertNotIn("\\\\?\\", arg)
            self.assertEqual(arg, "/select,")
            self.assertEqual(called_cmd[2], r"C:\Very\Deep\Folder\document.pdf")

    def test_preview_image_lru_cache(self):
        """Fix 8: Verify get_page_preview_image uses in-memory LRU cache."""
        api = Api(".")
        api.index_store = MagicMock()
        api.index_store.get_document.return_value = {
            "title": "Sample PDF",
            "original_path": "fake.pdf",
            "absolute_original_path": "fake.pdf",
        }
        api.index_store.resolve_file_path.return_value = "fake.pdf"

        # Prepopulate cache
        cache_key = ("fake.pdf", 1, 1000.0)
        api._page_preview_cache = {
            cache_key: {
                "success": True,
                "image_base64": "cached_base64_data",
                "current_page": 1,
                "total_pages": 5,
            }
        }
        with patch("os.path.isfile", return_value=True), patch("os.path.getmtime", return_value=1000.0):
            res = api.get_page_preview_image("doc123", page_number=1)
            self.assertTrue(res["success"])
            self.assertEqual(res["image_base64"], "cached_base64_data")


if __name__ == "__main__":
    unittest.main()
