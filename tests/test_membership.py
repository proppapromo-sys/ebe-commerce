import os
import tempfile
import unittest

from ebe.store import Store
from ebe import membership as m


class TierForTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(m.tier_for(0)["key"], "launch")
        self.assertEqual(m.tier_for(1)["key"], "bronze")
        self.assertEqual(m.tier_for(999)["key"], "bronze")
        self.assertEqual(m.tier_for(1000)["key"], "silver")
        self.assertEqual(m.tier_for(5000)["key"], "gold")
        self.assertEqual(m.tier_for(25000)["key"], "platinum")
        self.assertEqual(m.tier_for(100000)["key"], "diamond")
        self.assertEqual(m.tier_for(500000)["key"], "diamond")

    def test_next_tier(self):
        self.assertEqual(m.next_tier(m.tier_for(0))["key"], "bronze")
        self.assertEqual(m.next_tier(m.tier_for(2000))["key"], "gold")
        self.assertIsNone(m.next_tier(m.tier_for(200000)))


class StatusTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        # product priced so revenue is easy to reason about
        self.s.upsert_products([{"sku": "A", "name": "Thing", "cost": 1, "sell": 100, "on_hand": 1000}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_launch_when_no_sales(self):
        st = m.status(self.s)
        self.assertEqual(st["tier"]["key"], "launch")
        self.assertEqual(st["revenue"], 0)
        self.assertEqual(st["next"]["key"], "bronze")

    def test_progress_to_next(self):
        self.s.record_sale("A", 30)                 # $3,000 revenue → silver (1000..5000)
        st = m.status(self.s)
        self.assertEqual(st["tier"]["key"], "silver")
        self.assertEqual(st["next"]["key"], "gold")
        # 3000 is halfway from 1000 to 5000
        self.assertAlmostEqual(st["progress"], (3000 - 1000) / (5000 - 1000), places=3)
        self.assertEqual(st["to_next"], 2000.0)

    def test_diamond_has_no_next(self):
        self.s.record_sale("A", 1500)               # $150,000 → diamond
        st = m.status(self.s)
        self.assertEqual(st["tier"]["key"], "diamond")
        self.assertIsNone(st["next"])
        self.assertEqual(st["progress"], 1.0)

    def test_render_text(self):
        self.s.record_sale("A", 30)
        out = m.render_text(m.status(self.s))
        self.assertIn("MEMBERSHIP", out)
        self.assertIn("SILVER", out)
        self.assertIn("Gold", out)                  # next tier shown in the ladder


if __name__ == "__main__":
    unittest.main()
