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
    def test_personalisation_changes_the_shortlist(self):
        rows = sample_market()
        hookah_ids = {t[0]["id"] for t in scout.build(rows, PROFILES["hookah"], AMAZON_FBA).cycle()}
        generic_ids = {t[0]["id"] for t in scout.build(rows, PROFILES["generic"], AMAZON_FBA).cycle()}
        # the hookah operator pursues hookah lanes the generic seller's thinner-margin gate skips
        self.assertIn("hk_coco", hookah_ids)               # thin ROI, but their advantage clears it
        self.assertNotIn("hk_coco", generic_ids)
        self.assertNotEqual(hookah_ids, generic_ids)

    def test_landscape_ranks_by_roi_plus_fit(self):
        rows = sample_market()
        lm = landscape(rows, PROFILES["hookah"], AMAZON_FBA)
        cats = [r["category"] for r in lm]
        # every category is summarised exactly once
        self.assertEqual(len(cats), len(set(cats)))
        # hookah carries the operator's advantage in the map
        hk = next(r for r in lm if r["category"] == "hookah")
        self.assertEqual(hk["fit"], 0.30)


if __name__ == "__main__":
    unittest.main()
