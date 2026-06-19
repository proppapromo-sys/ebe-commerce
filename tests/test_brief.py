import os
import tempfile
import unittest

from ebe.store import Store
from ebe import brief, autobuy


class BriefTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "M2-Navy", "name": "Cap Navy", "category": "apparel", "cost": 7, "sell": 24,
             "lead_time_days": 25, "on_hand": 5, "monthly_sales": 150, "supplier": "Mill"},
            {"sku": "P1", "name": "LED", "category": "home", "cost": 5, "sell": 22,
             "lead_time_days": 18, "on_hand": 900, "monthly_sales": 80, "supplier": "Imports"},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_compose_counts_low_stock_and_value(self):
        b = brief.compose(self.s, profile="hookah")
        self.assertEqual(b["products"], 2)
        self.assertEqual(b["low"], 1)                     # only the cap is under the line
        self.assertGreater(b["cash_to_commit"], 0)
        self.assertGreater(b["inv_value"], 0)             # 900*5 + 5*7 on-hand value

    def test_one_move_prioritises_rebuy_then_send(self):
        self.assertIn("re-buys", brief.compose(self.s)["move"])
        autobuy.scan(self.s)                              # now there are drafts, nothing left under line
        b = brief.compose(self.s)
        self.assertEqual(b["low"], 0)
        self.assertIn("Send", b["move"])

    def test_render_text_is_a_readable_rundown(self):
        txt = brief.render_text(brief.compose(self.s), "Friday 19 June 2026")
        self.assertIn("MORNING BRIEF", txt)
        self.assertIn("Good morning", txt)
        self.assertIn("ONE MOVE", txt)

    def test_empty_db_tells_you_to_load_catalog(self):
        fd, p = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            empty = Store(p)
            b = brief.compose(empty)
            self.assertEqual(b["products"], 0)
            self.assertIn("catalog", b["move"])
            empty.close()
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
