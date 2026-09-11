import unittest
import sys
import os

sys.path.insert(0, os.path.abspath('src'))
from html_builder import markdown_to_html_body, build_html_document


class TestHtmlBuilder(unittest.TestCase):
    def test_hashtag_without_space_no_infinite_loop(self):
        sample = """
#Za9 4N kỆ
- I 19D $
###AnotherNoSpace
Some normal text
"""
        html = markdown_to_html_body(sample)
        self.assertIn("#Za9 4N kỆ", html)
        self.assertIn("AnotherNoSpace", html)

    def test_empty_list_markers(self):
        sample = """
* 
- 
1. 
Normal paragraph
"""
        html = markdown_to_html_body(sample)
        self.assertIn("Normal paragraph", html)

    def test_phu_luc_02_actual_file_conversion(self):
        md_path = os.path.join(
            "build_artifacts", "runtime", "MARKDOWN", "ae4b1c84f285e8b00c72",
            "3. Ho so nang luc kinh nghiem", "402518 - Phenikka",
            "2. Phụ lục 02 - SO 402518 phenikaa_CG.pdf.a962e72ce0ca6d76.md"
        )
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            html = markdown_to_html_body(content)
            self.assertGreater(len(html), 1000)
            self.assertIn("PHU LUC HỢP DONG SO 02", html)
            self.assertIn("#Za9 4N kỆ", html)


if __name__ == "__main__":
    unittest.main()
