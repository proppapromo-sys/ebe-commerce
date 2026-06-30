import unittest

from ebe.profile import Profile, PROFILES
from ebe.branches import scout
from ebe.branches.scout import ScoutEdge, landscape, sample_market
from ebe.fees import AMAZON_FBA


class ProfileTests(unittest.TestCase):
    def test_fit_bonus_by_category(self):
        p = PROFILES["hookah"]
        self.assertEqual(p.fit({"category": "hookah"}), 0.30)
        self.assertEqual(p.fit({"category": "kitchen"}), 0.0)

    def test_appetite_sets_gates(self):
        self.assertLess(PROFILES["aggressive"].risk()["min_edge"],
                        PROFILES["cautious"].risk()["min_edge"])


class ScoutEdgeTests(unittest.TestCase):
    def test_advantage_raises_edge_for_your_turf(self):
        item = {"category": "hookah", "sell": 15, "cost": 3}
        generic = ScoutEdge(PROFILES["generic"], AMAZON_FBA).edge(dict(item))
        hookah = ScoutEdge(PROFILES["hookah"], AMAZON_FBA).edge(dict(item))
        self.assertAlmostEqual(hookah - generic, 0.30)     # exactly the hookah fit bonus


class ScoutRunTests(unittest.TestCase):
    # explicit fixture: a thin-ROI item in the hookah operator's own turf, plus a generic one.
    ROWS = [
        {"id": "hk_coco", "name": "Coconut charcoal", "category": "hookah", "sell": 22, "cost": 9,
         "monthly_sales": 1200, "competition": 0.50},
        {"id": "kt_chop", "name": "Vegetable chopper", "category": "kitchen", "sell": 24, "cost": 6,
         "monthly_sales": 1500, "competition": 0.90},
    ]

    def test_personalisation_changes_the_shortlist(self):
        hookah_ids = {t[0]["id"] for t in scout.build(self.ROWS, PROFILES["hookah"], AMAZON_FBA).cycle()}
        generic_ids = {t[0]["id"] for t in scout.build(self.ROWS, PROFILES["generic"], AMAZON_FBA).cycle()}
        # the hookah operator pursues a hookah lane the generic seller's thinner-margin gate skips
        self.assertIn("hk_coco", hookah_ids)               # thin ROI, but their advantage clears it
        self.assertNotIn("hk_coco", generic_ids)
        self.assertNotEqual(hookah_ids, generic_ids)

    def test_landscape_ranks_by_roi_plus_fit(self):
        lm = landscape(self.ROWS, PROFILES["hookah"], AMAZON_FBA)
        cats = [r["category"] for r in lm]
        self.assertEqual(len(cats), len(set(cats)))        # every category summarised once
        hk = next(r for r in lm if r["category"] == "hookah")
        self.assertEqual(hk["fit"], 0.30)                  # hookah carries the operator's advantage


if __name__ == "__main__":
    unittest.main()
