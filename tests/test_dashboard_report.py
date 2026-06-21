import os
import tempfile
import types
import unittest

from ebe import dashboard as d
from ebe.store import Store


class DashboardReportTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = Store(self.path)
        s.upsert_products([
            {"sku": "WIN", "name": "High Margin", "cost": 2, "sell": 30, "monthly_sales": 400},
            {"sku": "DOG", "name": "Thin Margin", "cost": 9, "sell": 10, "monthly_sales": 5},
        ])
        s.close()
        self.a = types.SimpleNamespace(profile="hookah", fees="amazon-fba",
                                       capital=None, db=self.path, ai=False)

    def tearDown(self):
        os.remove(self.path)

    def test_report_tab_renders_score_without_ai(self):
        html = d.render_report(self.a)
        self.assertIn("EBE Orb", html)
        self.assertIn("Catalog score", html)
        self.assertIn("High Margin", html)
        self.assertIn("Ask EBE Orb to brief me", html)   # AI is opt-in

    def test_report_tab_in_nav(self):
        self.assertTrue(any(k == "report" for _, _, k in d.NAV))


if __name__ == "__main__":
    unittest.main()
