import os
import tempfile
import unittest

from ebe.store import Store
from ebe import alerts


def _kinds(a):
    return {x["kind"] for x in a}


class AlertsTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_stockout_is_critical(self):
        self.s.upsert_products([{"sku": "A", "name": "Fast", "cost": 2, "sell": 30,
                                 "on_hand": 5, "monthly_sales": 300, "lead_time_days": 21}])
        a = alerts.scan(self.s)
        self.assertIn("stockout", _kinds(a))
        crit = [x for x in a if x["kind"] == "stockout"][0]
        self.assertEqual(crit["level"], "critical")
        self.assertEqual(a[0]["level"], "critical")          # most urgent first

    def test_below_floor_warns(self):
        self.s.upsert_products([{"sku": "B", "name": "Thin", "cost": 9, "sell": 10,
                                 "on_hand": 5000, "monthly_sales": 5}])
        a = alerts.scan(self.s)
        self.assertIn("below_floor", _kinds(a))

    def test_reorder_alert(self):
        self.s.upsert_products([{"sku": "C", "name": "Low", "cost": 2, "sell": 30,
                                 "on_hand": 0, "monthly_sales": 100, "lead_time_days": 14}])
        a = alerts.scan(self.s)
        self.assertIn("reorder", _kinds(a))

    def test_top_seller_info(self):
        self.s.upsert_products([{"sku": "D", "name": "Hot", "cost": 2, "sell": 30,
                                 "on_hand": 9000, "monthly_sales": 5}])
        self.s.record_sale("D", 12)
        a = alerts.scan(self.s)
        self.assertIn("top_seller", _kinds(a))

    def test_all_clear(self):
        self.s.upsert_products([{"sku": "E", "name": "Fine", "cost": 2, "sell": 30,
                                 "on_hand": 100000, "monthly_sales": 5}])
        a = alerts.scan(self.s)
        self.assertEqual(a, [])
        self.assertIn("All clear", alerts.render_text(a))

    def test_summarize_counts(self):
        self.s.upsert_products([{"sku": "A", "name": "Fast", "cost": 2, "sell": 30,
                                 "on_hand": 5, "monthly_sales": 300, "lead_time_days": 21}])
        s = alerts.summarize(alerts.scan(self.s))
        self.assertGreaterEqual(s["critical"], 1)
        self.assertEqual(s["total"], s["critical"] + s["warn"] + s["info"])


if __name__ == "__main__":
    unittest.main()
