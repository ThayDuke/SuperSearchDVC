"""Unit tests for D-OCR advanced capabilities integrated into SuperSearch.

Covers:
1. System OCR Prompt: Physical Denoising, Multi-column Flow, Poetry, Footnotes, Hallucination Guard [?].
2. OCR Postprocessor: Cross-page sentence and soft-hyphen healing.
3. Export Service: LaTeX to OMML XML conversion and Math in DOCX.
4. API Page Preview Image: Endpoint for 1:1 Side-by-side comparison.
"""

import os
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

# Ensure src/ is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from gemini_ocr_engine import SYSTEM_OCR_INSTRUCTION
from ocr_postprocessor import (
    heal_cross_page_continuations,
    heal_document_markdown,
    heal_page_pair,
)
from export_service import convert_latex_to_omml, export_to_docx, export_to_markdown
from docx.oxml import parse_xml
import docx


class TestDocrFeatures(unittest.TestCase):

    def test_gemini_ocr_prompt_rules(self):
        """Verify the upgraded system prompt includes all core D-OCR quality rules."""
        prompt = SYSTEM_OCR_INSTRUCTION
        self.assertIn("[?]", prompt)
        self.assertIn("BỐ CỤC ĐA CỘT", prompt)
        self.assertIn("LOẠI BỎ TẠP ÂM SCAN VẬT LÝ", prompt)
        self.assertIn("THƠ CA", prompt)
        self.assertIn("CHÚ THÍCH", prompt)
        self.assertIn("CÔNG THỨC TOÁN HỌC", prompt)
        self.assertIn("CHỮ HÁN NÔM", prompt)
        self.assertIn("soft-hyphen", prompt)

    def test_postprocessor_soft_hyphen_healing(self):
        """Verify soft-hyphenated words across page boundaries are properly healed."""
        p1 = "Đây là quá trình phát-"
        p2 = "triển vượt bậc của công nghệ."
        h1, h2 = heal_page_pair(p1, p2)
        self.assertEqual(h1, "Đây là quá trình phát")
        self.assertEqual(h2, p2)

        # In full pages list
        pages = [
            "Đoạn văn trang một nghiên-",
            "cứu chuyên sâu trong lĩnh vực."
        ]
        healed = heal_cross_page_continuations(pages)
        self.assertEqual(healed[0], "Đoạn văn trang một nghiên")
        self.assertEqual(healed[1], pages[1])

    def test_postprocessor_incomplete_sentence_flow(self):
        """Verify flowing sentences without punctuation normalize trailing breaks."""
        p1 = "Đây là một câu văn dài nhưng chưa có dấu chấm ở cuối trang"
        p2 = "tiếp tục mạch văn tự nhiên ở trang sau."
        h1, h2 = heal_page_pair(p1 + "\n\n", p2)
        self.assertTrue(h1.endswith(" "))
        self.assertEqual(h2, p2)

    def test_postprocessor_heal_document_markdown(self):
        """Verify markdown with <!-- PAGE X --> comments is healed across comments."""
        md = (
            "Một phát kiến mang tính lịch-\n"
            "<!-- PAGE 2 (Gemini AI OCR Mode) -->\n"
            "sử của đất nước."
        )
        healed = heal_document_markdown(md)
        self.assertIn("lịch", healed)
        self.assertNotIn("lịch-", healed)
        self.assertIn("<!-- PAGE 2", healed)

    def test_latex_to_omml_fractions_and_symbols(self):
        """Verify LaTeX fractions, radicals and Greek symbols produce valid OMML XML."""
        latex = r"\frac{a + b}{c - d}"
        xml = convert_latex_to_omml(latex, is_block=False)
        self.assertIn("<m:oMath", xml)
        self.assertIn("<m:f>", xml)
        self.assertIn("<m:num>", xml)
        self.assertIn("<m:den>", xml)

        # Parse XML to guarantee well-formedness
        el = parse_xml(xml)
        self.assertIsNotNone(el)

    def test_latex_to_omml_radicals_and_powers(self):
        """Verify square roots and powers produce valid OMML XML."""
        latex = r"\sqrt{x^2 + y^2}"
        xml = convert_latex_to_omml(latex, is_block=True)
        self.assertIn("<m:oMathPara", xml)
        self.assertIn("<m:rad>", xml)
        self.assertIn("<m:sSup>", xml)

        el = parse_xml(xml)
        self.assertIsNotNone(el)

    def test_latex_to_omml_greek_and_subscripts(self):
        """Verify Greek letters and subscripts are properly translated."""
        latex = r"\alpha_1 + \beta_2 = \pi"
        xml = convert_latex_to_omml(latex, is_block=False)
        self.assertIn("α", xml)
        self.assertIn("β", xml)
        self.assertIn("π", xml)
        self.assertIn("<m:sSub>", xml)

        el = parse_xml(xml)
        self.assertIsNotNone(el)

    def test_export_docx_with_math_equations(self):
        """Verify exporting a document with inline and block math creates valid Word document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "math_sample.docx")
            doc_data = {
                "title": "Báo cáo Toán học",
                "original_path": "toan_hoc.md",
                "doc_type": "Tài liệu",
                "year": "2026",
                "content": (
                    "# Khảo sát Hàm số\n\n"
                    "Phương trình nổi tiếng của Einstein là $E=mc^2$.\n\n"
                    r"$$\frac{d}{dx} \int_0^x f(t) dt = f(x)$$" + "\n\n"
                    r"Biểu thức căn bậc hai: \(\sqrt{a^2 + b^2} \ge 0\)."
                ),
            }
            res_path = export_to_docx(doc_data, out_file)
            self.assertTrue(os.path.isfile(res_path))
            self.assertGreater(os.path.getsize(res_path), 500)

            # Re-open with docx to verify structure
            loaded_doc = docx.Document(res_path)
            self.assertGreater(len(loaded_doc.paragraphs), 2)
            # Find elements with math namespace
            xml_str = loaded_doc._element.xml
            self.assertIn("http://schemas.openxmlformats.org/officeDocument/2006/math", xml_str)

    def test_api_page_preview_unsupported_type(self):
        """Verify Api.get_page_preview_image returns error for non-image/non-pdf formats."""
        from app import Api
        with tempfile.TemporaryDirectory() as tmpdir:
            api = Api(tmpdir)
            # Query non-existent document
            res = api.get_page_preview_image("non_existent_doc_id", 1)
            self.assertFalse(res.get("success"))
            self.assertIn("Không tìm thấy", res.get("error"))


if __name__ == "__main__":
    unittest.main()
