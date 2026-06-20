import unittest

from ebe.scanner import scan
from ebe.profile import PROFILES


def _fake_fetch(category=None, **kw):
    catalog = {
        "hookah": [
            {"id": "B1", "name": "Coco charcoal", "category": "hookah", "cost": 3.0,
             "sell": 14.99, "monthly_sales": 1000, "competition": 0.4},
        ],
        "home": [
            {"id": "B2", "name": "LED coaster", "category": "home", "cost": 2.4,
             "sell": 11.99, "monthly_sales": 200, "competition": 0.8},
            {"id": "B1", "name": "Coco charcoal (dup)", "category": "home", "cost": 3.0,
             "sell": 14.99, "monthly_sales": 1000, "competition": 0.4},   # duplicate id
        ],
    }
    return catalog.get(category, [])


class ScannerTests(unittest.TestCase):
    def test_scan_combs_multiple_categories_and_dedups(self):
        deals = scan(_fake_fetch, ["hookah", "home"], PROFILES["hookah"])
        ids = [d["id"] for d in deals]
        self.assertEqual(ids.count("B1"), 1)               # de-duped across categories
        self.assertIn("B2", ids)

    def test_best_opportunity_ranks_first(self):
        deals = scan(_fake_fetch, ["hookah", "home"], PROFILES["hookah"])
        self.assertEqual(deals[0]["id"], "B1")             # charcoal: high edge × margin × demand
        for d in deals:
            self.assertIn("best_channel", d)
            self.assertIn("deal_score", d)

    def test_category_with_no_results_is_skipped(self):
        deals = scan(_fake_fetch, ["nonexistent"], PROFILES["hookah"])
        self.assertEqual(deals, [])

    def test_fetch_error_does_not_crash_the_sweep(self):
        def boom(category=None, **kw):
            if category == "bad":
                raise RuntimeError("api down")
            return _fake_fetch(category=category)
        deals = scan(boom, ["bad", "hookah"], PROFILES["hookah"])
        self.assertTrue(any(d["id"] == "B1" for d in deals))   # good category still scanned


if __name__ == "__main__":
    unittest.main()
