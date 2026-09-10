import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app import DynamicWorkerRegulator


class TestDynamicWorkerRegulator(unittest.TestCase):
    def test_green_zone_full_capacity(self):
        ram_val = 50
        regulator = DynamicWorkerRegulator(lambda: ram_val, base_workers=8)
        regulator.update_limits()
        self.assertEqual(regulator.current_allowed, 8)

    def test_yellow_zone_soft_throttle(self):
        ram_val = 70  # 65% - 75%
        regulator = DynamicWorkerRegulator(lambda: ram_val, base_workers=8)
        regulator.update_limits()
        # max(2, int(8 * 0.65)) = 5
        self.assertEqual(regulator.current_allowed, 5)

    def test_red_zone_user_75_percent_cap(self):
        ram_val = 78  # > 75%
        regulator = DynamicWorkerRegulator(lambda: ram_val, base_workers=8)
        regulator.update_limits()
        # max(2, int(8 * 0.35)) = 2 (not choked to 1 thread!)
        self.assertEqual(regulator.current_allowed, 2)

    def test_emergency_zone_above_88_percent(self):
        ram_val = 92  # > 88%
        regulator = DynamicWorkerRegulator(lambda: ram_val, base_workers=8)
        regulator.update_limits()
        self.assertEqual(regulator.current_allowed, 1)

    def test_hysteresis_recovery(self):
        ram_holder = [80]
        regulator = DynamicWorkerRegulator(lambda: ram_holder[0], base_workers=8)
        regulator.update_limits()
        self.assertEqual(regulator.current_allowed, 2)

        # Drop to 63% (below 65% but not below 60%) -> should not immediately jump to 8
        ram_holder[0] = 63
        regulator.sample_ram(force=True)
        regulator.update_limits()
        self.assertNotEqual(regulator.current_allowed, 8)

        # Drop to 55% cycle 1
        ram_holder[0] = 55
        regulator.sample_ram(force=True)
        regulator.update_limits()
        # Drop to 55% cycle 2 -> satisfies hysteresis (streak >= 2)
        regulator.sample_ram(force=True)
        regulator.update_limits()
        self.assertEqual(regulator.current_allowed, 8)

    def test_abort_releases_acquire(self):
        regulator = DynamicWorkerRegulator(lambda: 50, base_workers=1)
        acquired = regulator.acquire(abort_check=lambda: False)
        self.assertTrue(acquired)
        # Next acquire should abort when abort_check is True
        aborted = regulator.acquire(abort_check=lambda: True)
        self.assertFalse(aborted)
        regulator.release()


if __name__ == '__main__':
    unittest.main()
