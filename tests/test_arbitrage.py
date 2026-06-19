import unittest

from ebe.arbitrage import signal, cross_channel, PriceSource
from ebe.adapters.keepa import keepa_price_points
from ebe.edges import arbitrage_edge


class TemporalSignalTests(unittest.TestCase):
    def test_buy_the_dip_when_cheap_and_near_low(self):
        s = signal({"current": 18.5, "avg": 22.0, "min": 18.0, "max": 26.0})
        self.assertGreater(s.dip, 0.10)          # ~16% below average
        self.assertEqual(s.verdict, "BUY THE DIP")
        self.assertGreater(s.edge, 0.5)

    def test_above_average_is_not_a_buy(self):
        s = signal({"current": 24.0, "avg": 22.0, "min": 18.0, "max": 26.0})
        self.assertLess(s.dip, 0)
        self.assertNotEqual(s.verdict, "BUY THE DIP")

    def test_missing_data_returns_none(self):
        self.assertIsNone(signal({"current": 0, "avg": 0}))


class CrossChannelTests(unittest.TestCase):
    def test_best_buy_low_sell_high(self):
        class Src(PriceSource):
            def __init__(self, name, p): self.name, self._p = name, p
            def price(self, ident): return self._p
        out = cross_channel("X", [Src("amazon", 20.0), Src("walmart", 14.0)])
        self.assertEqual(out["buy_channel"], "walmart")
        self.assertEqual(out["sell_channel"], "amazon")
        self.assertAlmostEqual(out["edge"], 1.0)          # 30% gap = full

    def test_needs_two_quotes(self):
        class Src(PriceSource):
            name = "only"
            def price(self, ident): return 10.0
        self.assertIsNone(cross_channel("X", [Src()]))


class KeepaPointsTests(unittest.TestCase):
    def test_parses_flat_and_pair_shapes(self):
        # avg is a flat per-type array; min/max are [timestamp, cents] pairs per type
        n = 20
        avg = [-1] * n; avg[18] = 2200          # $22.00 buy box
        cur = [-1] * n; cur[18] = 2000          # $20.00 now
        lo = [[0, 0]] * n; lo[18] = [123, 1800]  # $18.00 low
        hi = [[0, 0]] * n; hi[18] = [123, 2600]  # $26.00 high
        kp = {"stats": {"current": cur, "avg": avg, "min": lo, "max": hi}}
        pts = keepa_price_points(kp)
        self.assertAlmostEqual(pts["current"], 20.0)
        self.assertAlmostEqual(pts["avg"], 22.0)
        self.assertAlmostEqual(pts["min"], 18.0)
        self.assertAlmostEqual(pts["max"], 26.0)


class EdgeWiringTests(unittest.TestCase):
    def test_arbitrage_edge_honours_live_score(self):
        self.assertAlmostEqual(arbitrage_edge({"arb_edge": 0.8}), 0.8)
        self.assertEqual(arbitrage_edge({"sell": 20}), 0.5)     # unknown -> neutral


if __name__ == "__main__":
    unittest.main()
