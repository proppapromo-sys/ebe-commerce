import os
import tempfile
import unittest

from ebe.store import Store
from ebe import shrinkage


class ShrinkageTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            # fast mover, short cover vs a long lead time → stockout risk
            {"sku": "CHARCOAL", "name": "Charcoal", "cost": 6, "sell": 0,
             "lead_time_days": 20, "on_hand": 30, "monthly_sales": 300},
            # well stocked → no risk
            {"sku": "P1", "name": "LED", "cost": 5, "sell": 22,
             "lead_time_days": 18, "on_hand": 900, "monthly_sales": 80},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_stockout_risk_flags_short_cover(self):
        risk = shrinkage.stockout_risk(self.s)
        skus = [r["sku"] for r in risk]
        self.assertIn("CHARCOAL", skus)          # 30 / (300/30=10) = 3 days vs 20 lead → will stock out
        self.assertNotIn("P1", skus)
        ch = next(r for r in risk if r["sku"] == "CHARCOAL")
        self.assertTrue(ch["stockout"])

    def test_record_count_detects_shrinkage_and_values_it(self):
        # system thinks 30, physical count is 22 → 8 units gone
        res = shrinkage.record_count(self.s, "CHARCOAL", 22)
        self.assertEqual(res["variance"], -8)
        self.assertEqual(res["value"], -48.0)    # 8 × $6
        self.assertEqual(self.s.product("CHARCOAL")["on_hand"], 22)   # set to truth

    def test_overage_is_not_shrinkage(self):
        res = shrinkage.record_count(self.s, "P1", 950)   # found 50 extra
        self.assertEqual(res["variance"], 50)
        self.assertEqual(res["value"], 0.0)               # overage isn't a loss

    def test_shrinkage_report_aggregates_value(self):
        shrinkage.record_count(self.s, "CHARCOAL", 22)    # -8 × $6 = $48
        shrinkage.record_count(self.s, "P1", 880)         # -20 × $5 = $100
        rep = shrinkage.shrinkage_report(self.s)
        self.assertEqual(rep["units_lost"], 28)
        self.assertEqual(rep["value_lost"], 148.0)
        self.assertEqual(rep["by_sku"][0]["sku"], "P1")   # ranked by $ value


if __name__ == "__main__":
    unittest.main()
