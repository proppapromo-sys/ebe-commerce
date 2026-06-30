import os
import time
import tempfile
import unittest

from ebe.store import Store
from ebe import pnl


class PnlTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 100},
            {"sku": "B", "name": "Beta", "cost": 3, "sell": 15, "on_hand": 100},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_revenue_cogs_gross(self):
        self.s.record_sale("A", 5)
        self.s.record_sale("B", 2)
        p = pnl.compute(self.s)
        t = p["totals"]
        self.assertEqual(t["units"], 7)
        self.assertEqual(t["revenue"], 80.0)          # 5*10 + 2*15
        self.assertEqual(t["cogs"], 16.0)             # 5*2 + 2*3
        self.assertEqual(t["gross"], 64.0)
        self.assertAlmostEqual(t["margin"], 64.0 / 80.0)

    def test_per_sku_sorted_by_gross(self):
        self.s.record_sale("A", 5)                     # gross 40
        self.s.record_sale("B", 2)                     # gross 24
        rows = pnl.compute(self.s)["rows"]
        self.assertEqual(rows[0]["sku"], "A")
        self.assertEqual(rows[0]["gross"], 40.0)
        self.assertEqual(rows[1]["gross"], 24.0)

    def test_days_window_excludes_old_sales(self):
        # an old sale 40 days ago, inserted directly with an old ts
        old = time.time() - 40 * 86400
        self.s._cx.execute("INSERT INTO events (ts,kind,sku,qty) VALUES (?,?,?,?)",
                           (old, "sale", "A", -10))
        self.s._cx.commit()
        self.s.record_sale("A", 5)                     # recent
        recent = pnl.compute(self.s, days=30)
        self.assertEqual(recent["totals"]["units"], 5)     # old one excluded
        alltime = pnl.compute(self.s, days=None)
        self.assertEqual(alltime["totals"]["units"], 15)

    def test_empty_renders_guidance(self):
        out = pnl.render_text(pnl.compute(self.s))
        self.assertIn("No recorded sales", out)


if __name__ == "__main__":
    unittest.main()
