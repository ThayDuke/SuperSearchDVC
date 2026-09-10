import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import Api


class TestProgressCalculation(unittest.TestCase):
    def test_weighted_progress_and_subprogress(self):
        api = Api(".")
        
        # Setup simulated tasks: one 50MB PDF and one 1MB text
        heavy_id = os.path.normcase(os.path.normpath(os.path.abspath("heavy.pdf")))
        light_id = os.path.normcase(os.path.normpath(os.path.abspath("light.txt")))
        
        total_bytes = 51 * 1024 * 1024
        total_tasks = 2
        
        api._task_weights = {
            heavy_id: 0.70 * (50 * 1024 * 1024 / total_bytes) + 0.30 * 0.5,
            light_id: 0.70 * (1 * 1024 * 1024 / total_bytes) + 0.30 * 0.5,
        }
        api._task_subprogress = {
            heavy_id: 0.0,
            light_id: 0.0,
        }
        api._completed_weights = 0.0
        
        reports = []
        api._report_progress = lambda percent, active_list: reports.append((percent, active_list))
        
        # At start, baseline
        api._recalculate_and_report_progress()
        self.assertTrue(len(reports) > 0)
        self.assertEqual(reports[-1][0], 2)  # Baseline 2%
        
        # Heavy PDF completes 50% (e.g. page 10 of 20)
        api.update_task_subprogress("heavy.pdf", fraction=0.5, status_text="Trang 10/20")
        self.assertGreater(reports[-1][0], 2)  # Should smoothly advance beyond 2%
        
        # Light file completes
        api._completed_weights += api._task_weights[light_id]
        api._task_subprogress.pop(light_id, None)
        api._recalculate_and_report_progress()
        
        intermediate_percent = reports[-1][0]
        self.assertGreater(intermediate_percent, 10)
        
        # Heavy file finishes
        api._completed_weights += api._task_weights[heavy_id]
        api._task_subprogress.pop(heavy_id, None)
        api._recalculate_and_report_progress()
        self.assertEqual(reports[-1][0], 98)  # Final conversion stage reaches 98% before commit to 100%


if __name__ == '__main__':
    unittest.main()
