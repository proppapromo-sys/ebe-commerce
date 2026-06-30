import os
import tempfile
import unittest

from ebe.store import Store
from ebe import report


class ReportTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "WIN", "name": "High Margin", "cost": 2, "sell": 30, "monthly_sales": 400},
            {"sku": "DOG", "name": "Thin Margin", "cost": 9, "sell": 10, "monthly_sales": 5},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_compose_gathers_brief_and_score(self):
        data = report.compose(self.s, profile="hookah")
        self.assertIn("brief", data)
        self.assertEqual(data["summary"]["count"], 2)
        self.assertEqual(len(data["ranked"]), 2)
        # high-margin SKU should rank first
        self.assertEqual(data["ranked"][0]["name"], "High Margin")

    def test_facts_includes_score_lines(self):
        data = report.compose(self.s, profile="hookah")
        fs = report.facts(data)
        self.assertIn("Catalog score", fs)
        self.assertIn("High Margin", fs)
        self.assertIn("Thin Margin", fs)

    def test_write_uses_assess_fn_and_renders(self):
        data = report.compose(self.s, profile="hookah")
        fake = lambda fact_sheet: {
            "headline": "Strong week",
            "summary": "Charcoal is carrying the business.",
            "priorities": ["Reorder charcoal", "Drop the thin SKU"],
            "product_focus": "Push High Margin, reconsider Thin Margin.",
        }
        rep = report.write(data, assess_fn=fake)
        out = report.render_text(rep)
        self.assertIn("BUSINESS REPORT", out)
        self.assertIn("Strong week", out)
        self.assertIn("1. Reorder charcoal", out)
        self.assertIn("PRODUCT FOCUS", out)

    def test_facts_passed_to_assess(self):
        data = report.compose(self.s, profile="hookah")
        seen = {}
        def capture(fact_sheet):
            seen["fs"] = fact_sheet
            return {"headline": "h", "summary": "s", "priorities": [], "product_focus": "p"}
        report.write(data, assess_fn=capture)
        self.assertIn("Catalog score", seen["fs"])


if __name__ == "__main__":
    unittest.main()
