import unittest

from ebe.branches import returns
from ebe.branches.returns import return_rate, ReturnsEdge, build
from ebe.fees import AMAZON_FBA, MERCH_APPAREL


class ReturnsTests(unittest.TestCase):
    def test_return_rate(self):
        self.assertAlmostEqual(return_rate({"units_sold": 200, "units_returned": 50}), 0.25)
        self.assertEqual(return_rate({"units_sold": 0, "units_returned": 5}), 0.0)

    def test_edge_is_excess_over_category_baseline(self):
        edge = ReturnsEdge(AMAZON_FBA)
        apparel = {"category": "apparel", "units_sold": 100, "units_returned": 35}
        # 35% actual − 20% apparel baseline = +15% excess
        self.assertAlmostEqual(edge.edge(apparel), 0.35 - MERCH_APPAREL.return_rate)
        home = {"category": "home", "units_sold": 100, "units_returned": 5}
        # 5% actual − 5% home baseline = 0 (at norm)
        self.assertAlmostEqual(edge.edge(home), 0.05 - AMAZON_FBA.return_rate)

    def test_only_material_leaks_clear(self):
        m = build(fee_model=AMAZON_FBA)
        flagged = [t[0]["id"] for t in m.cycle()]
        self.assertIn("M1", flagged)        # tee: 35% vs 20% norm, big $ bleed
        self.assertIn("P3", flagged)        # yoga mat: 15% vs 5% norm
        self.assertNotIn("M2", flagged)     # cap: 20% == apparel norm
        self.assertNotIn("P1", flagged)     # LED: 5% == home norm

    def test_stake_is_recoverable_monthly_bleed(self):
        m = build(fee_model=AMAZON_FBA)
        ticket = next(t for t in m.cycle() if t[0]["id"] == "M1")
        item, stake = ticket
        # excess 15% × 300 sold = 45 returns/mo × (fulfilment 5 + cost 9) = $630
        self.assertAlmostEqual(stake, 630.0)


if __name__ == "__main__":
    unittest.main()
