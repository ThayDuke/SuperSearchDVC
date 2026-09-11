import os
import sys
import unittest
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import Api


class TestOcrCacheInvalidation(unittest.TestCase):
    def test_ocr_invalidation_when_upgrading_to_gemini(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            api = Api(temp_dir)
            source_pdf = os.path.join(temp_dir, "sample.pdf")
            with open(source_pdf, "wb") as f:
                f.write(b"%PDF-1.4 dummy pdf content for testing")

            md_path = os.path.join(temp_dir, "sample.pdf.md")
            
            # 1. First write markdown with local OCR tag
            api.gemini_api_key = ""
            api.ocr_engine = "hybrid"
            api._write_markdown(md_path, "Nội dung cũ", source_pdf, temp_dir)

            # At this point, without Gemini, cache is valid
            self.assertFalse(api._markdown_needs_refresh(md_path, source_pdf, temp_dir))

            # 2. User configures Gemini API Key
            api.gemini_api_key = "AIzaSyFakeKey123"
            api.gemini_model = "gemini-3.6-flash"
            api.ocr_engine = "hybrid"

            # Cache MUST be invalidated because it was written by local OCR without Gemini!
            self.assertTrue(api._markdown_needs_refresh(md_path, source_pdf, temp_dir))

            # 3. Once re-written with Gemini active:
            api._write_markdown(md_path, "Nội dung mới từ Gemini", source_pdf, temp_dir)
            self.assertFalse(api._markdown_needs_refresh(md_path, source_pdf, temp_dir))


if __name__ == '__main__':
    unittest.main()
