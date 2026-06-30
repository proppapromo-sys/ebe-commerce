import unittest

from ebe.repricer import floor_price, recommend, reprice_catalog
from ebe.fees import AMAZON_FBA


class RepricerTests(unittest.TestCase):
    def test_floor_price_earns_at_least_the_floor_roi(self):
        f = floor_price(7.0, AMAZON_FBA, floor_roi=0.30)
        self.assertGreaterEqual(AMAZON_FBA.roi(f, 7.0), 0.30 - 1e-6)
        # a cent under the floor must NOT clear it
        self.assertLess(AMAZON_FBA.roi(f - 0.5, 7.0), 0.30)

    def test_undercut_sits_just_below_market_low(self):
        r = recommend({"cost": 7, "sell": 24}, [21.99, 22.50, 23.00], AMAZON_FBA, strategy="undercut")
        self.assertAlmostEqual(r["recommended"], 21.98, places=2)
        self.assertEqual(r["market_low"], 21.99)
        self.assertFalse(r["at_floor"])

    def test_never_prices_below_floor(self):
        # rivals are dumping below our cost+fees → we refuse to chase, hold at floor
        r = recommend({"cost": 18, "sell": 30}, [12.00, 12.50], AMAZON_FBA, strategy="undercut")
        self.assertEqual(r["recommended"], r["floor"])
        self.assertTrue(r["at_floor"])
        self.assertGreaterEqual(r["roi"], 0.30 - 1e-6)

    def test_premium_sits_at_median_not_floor(self):
        r = recommend({"cost": 7, "sell": 24}, [20.00, 26.00, 30.00], AMAZON_FBA, strategy="premium")
        self.assertEqual(r["recommended"], 26.00)

    def test_no_competitors_holds_above_floor(self):
        r = recommend({"cost": 7, "sell": 24}, [], AMAZON_FBA)
        self.assertGreaterEqual(r["recommended"], r["floor"])
        self.assertIsNone(r["market_low"])

    def test_reprice_catalog_sorted_by_move(self):
        prods = [
            {"sku": "A", "name": "A", "cost": 7, "sell": 24},
            {"sku": "B", "name": "B", "cost": 7, "sell": 24},
        ]
        recs = reprice_catalog(prods, {"A": [22.00], "B": [19.00]}, AMAZON_FBA)
        self.assertEqual([r["sku"] for r in recs][0], "B")   # bigger price move first

    def test_live_prices_map_asins_to_skus(self):
        from ebe.repricer import live_prices_by_sku
        prods = [{"sku": "CAP", "asin": "B01", "cost": 7, "sell": 24},
                 {"sku": "NOASIN", "cost": 5, "sell": 20}]   # no asin → skipped

        def fetch(asins):
            self.assertEqual(asins, ["B01"])
            return [{"asin": "B01", "stats": {"buyBoxPrice": 2199, "current": [2250]}}]

        out = live_prices_by_sku(prods, fetch)
        self.assertIn("CAP", out)
        self.assertNotIn("NOASIN", out)
        self.assertIn(21.99, out["CAP"])     # buyBoxPrice cents → dollars


if __name__ == "__main__":
    unittest.main()
