import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core_utils import (
    safe_long_path,
    remove_diacritics,
    get_system_ram_load,
    get_safe_workers_count,
    ConversionPolicyError,
    SUPPORTED_EXTENSIONS,
)
from converters import (
    configure_tesseract,
    SafeZipConverter,
    create_markdown_converter,
)
from file_classifier import (
    clean_content,
    is_ocr_noise,
    infer_original_ext,
    calculate_ocr_quality_score,
    classify_source,
    detect_domain,
    detect_doc_type,
    detect_language,
)
from app import Api


class ModularDecompositionTests(unittest.TestCase):
    def test_core_utils_standalone(self):
        self.assertEqual(remove_diacritics("Đạt chuẩn ISO"), "dat chuan iso")
        self.assertIn(".pdf", SUPPORTED_EXTENSIONS)
        self.assertIn(".docx", SUPPORTED_EXTENSIONS)
        self.assertIn(".zip", SUPPORTED_EXTENSIONS)
        ram = get_system_ram_load()
        self.assertIsInstance(ram, int)
        self.assertGreaterEqual(ram, 0)
        self.assertLessEqual(ram, 100)
        workers = get_safe_workers_count()
        self.assertGreaterEqual(workers, 1)

    def test_file_classifier_standalone(self):
        cleaned = clean_content("<!-- ORIGINAL_PATH: foo.pdf -->\n# Header\nText")
        self.assertEqual(cleaned, "# Header\nText")
        self.assertEqual(infer_original_ext("report.pdf"), ".pdf")
        self.assertEqual(infer_original_ext("report.docx.md"), ".docx")
        self.assertTrue(is_ocr_noise("||||||||||||||||"))
        self.assertFalse(is_ocr_noise("Báo cáo tài chính năm 2026 của công ty"))
        quality = calculate_ocr_quality_score("Đây là nội dung văn bản hoàn chỉnh và chất lượng cao.")
        self.assertGreater(quality, 0.5)
        self.assertEqual(detect_language("Tài liệu hướng dẫn an toàn lao động"), "Tiếng Việt (VN)")
        en_sample = ("the procedure and manual of the report version date page document policy " * 2).lower()
        self.assertEqual(detect_language(en_sample), "Tiếng Anh (EN)")

    def test_converters_factory(self):
        class MockApi:
            base_dir = REPO_ROOT
            base_dir_exe = REPO_ROOT
            base_dir_meipass = REPO_ROOT
            ocr_lock = None
            ocr_engine = 'hybrid'
            gemini_api_key = ''
            gemini_model = 'gemini-3.6-flash'

        converter = create_markdown_converter(MockApi())
        self.assertIsNotNone(converter)

    def test_app_api_delegation(self):
        api = Api(REPO_ROOT)
        self.assertEqual(api._clean_content("<!-- ORIGINAL_PATH: foo.pdf -->Hello"), "Hello")
        self.assertEqual(api._infer_original_ext("test.docx.md"), ".docx")
        self.assertIsInstance(api.get_system_ram_load(), int)
        self.assertGreaterEqual(api.get_safe_workers_count(), 1)


if __name__ == '__main__':
    unittest.main()
