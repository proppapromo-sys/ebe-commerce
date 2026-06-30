import unittest

from ebe.timing import momentum
from ebe.adapters.keepa import keepa_rank_points, live_edge_item
from ebe.edges import timing_edge, score
from ebe.profile import PROFILES
from ebe.fees import AMAZON_FBA


class MomentumTests(unittest.TestCase):
    def test_rising_when_current_rank_beats_average(self):
        s, label = momentum({"current_rank": 800, "avg_rank": 1200})   # lower = better
        self.assertEqual(label, "rising")
        self.assertGreater(s, 0.5)

    def test_fading_when_rank_worsens(self):
        s, label = momentum({"current_rank": 1600, "avg_rank": 1200})
        self.assertEqual(label, "fading")
        self.assertLess(s, 0.5)

    def test_flat_and_unknown(self):
        self.assertEqual(momentum({"current_rank": 1000, "avg_rank": 1050})[1], "flat")
        self.assertEqual(momentum({})[1], "unknown")


class RankPointsTests(unittest.TestCase):
    def test_parses_sales_rank_index(self):
        n = 20
        cur = [-1] * n; cur[3] = 850          # index 3 = SALES rank
        avg = [-1] * n; avg[3] = 1300
        kp = {"stats": {"current": cur, "avg": avg}}
        pts = keepa_rank_points(kp)
        self.assertEqual(pts["current_rank"], 850)
        self.assertEqual(pts["avg_rank"], 1300)


class EdgeWiringTests(unittest.TestCase):
    def test_timing_edge_honours_live_score(self):
        self.assertAlmostEqual(timing_edge({"tim_edge": 0.82}), 0.82)
        self.assertEqual(timing_edge({}), 0.5)              # no signal -> neutral


class LiveAssemblyTests(unittest.TestCase):
    def test_live_edge_item_populates_arb_and_timing(self):
        n = 20
        cur = [-1] * n; cur[18] = 2000; cur[3] = 800       # price $20 (buybox), rank 800
        avg = [-1] * n; avg[18] = 2200; avg[3] = 1200      # avg price $22, avg rank 1200
        lo = [[0, 0]] * n; lo[18] = [1, 1800]
        hi = [[0, 0]] * n; hi[18] = [1, 2600]
        kp = {"asin": "B0TEST", "title": "Test widget", "monthlySold": 500,
              "categoryTree": [{"name": "Home"}],
              "stats": {"current": cur, "avg": avg, "min": lo, "max": hi,
                        "buyBoxPrice": 2000, "offerCountFBA": 6}}
        it = live_edge_item(kp, cost_ratio=0.35)
        self.assertIn("arb_edge", it)            # price is below its 90-day average -> arbitrage signal
        self.assertIn("tim_edge", it)            # rank improving -> rising momentum
        self.assertGreater(it["tim_edge"], 0.5)
        # the live signals flow into the fused true-edge score
        e = score(it, PROFILES["generic"], AMAZON_FBA)
        self.assertEqual(set(e.signals), {"margin", "demand", "competition", "advantage",
                                          "recurrence", "timing", "arbitrage"})


if __name__ == "__main__":
    unittest.main()
