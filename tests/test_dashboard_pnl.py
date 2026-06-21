import os
import tempfile
import types
import unittest

from ebe import dashboard as d
from ebe.store import Store


class DashboardPnlTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = Store(self.path)
        s.upsert_products([{"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 100}])
        s.record_sale("A", 5)
        s.close()
        self.a = types.SimpleNamespace(profile="generic", fees="amazon-fba",
                                       capital=None, db=self.path)

    def tearDown(self):
        os.remove(self.path)

    def test_pnl_tab_renders_profit(self):
        html = d.render_pnl(self.a)
        self.assertIn("Profit", html)
        self.assertIn("Alpha", html)
        self.assertIn("Gross profit", html)

    def test_pnl_in_nav(self):
        self.assertTrue(any(k == "pnl" for _, _, k in d.NAV))


class ReportIncludesPnlTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 100, "monthly_sales": 50}])
        self.s.record_sale("A", 5)

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_facts_mention_realized_profit(self):
        from ebe import report
        data = report.compose(self.s, profile="generic")
        self.assertIn("pnl", data)
        fs = report.facts(data)
        self.assertIn("Realized sales", fs)
        self.assertIn("gross profit", fs)


if __name__ == "__main__":
    unittest.main()
