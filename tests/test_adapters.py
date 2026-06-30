import os
import tempfile
import unittest

from ebe.adapters import config
from ebe.adapters.keepa import (
    to_product, keepa_sell_price, keepa_monthly_sales, keepa_competition, load_asin_costs,
)
from ebe.adapters.amazon_spapi import inventory_to_stock


class ConfigTests(unittest.TestCase):
    def test_load_env_parses_and_skips_comments(self):
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w") as fh:
            fh.write("# comment\nKEEPA_API_KEY=abc123\n\nQUOTED=\"hello\"\n")
        try:
            # existing env wins; ensure our keys aren't already set
            os.environ.pop("KEEPA_API_KEY", None)
            os.environ.pop("QUOTED", None)
            config._LOADED = False
            config.load_env(path)
            self.assertEqual(config.get("KEEPA_API_KEY"), "abc123")
            self.assertEqual(config.get("QUOTED"), "hello")
        finally:
            os.remove(path)
            os.environ.pop("KEEPA_API_KEY", None)
            os.environ.pop("QUOTED", None)

    def test_require_reports_missing(self):
        os.environ.pop("DEFINITELY_MISSING_KEY", None)
        self.assertEqual(config.require(["DEFINITELY_MISSING_KEY"]), ["DEFINITELY_MISSING_KEY"])


# A synthetic Keepa product object (shape per keepa.com product docs).
KEEPA_OBJ = {
    "asin": "B0EXAMPLE01",
    "title": "Stainless Steel Water Bottle 32oz",
    "monthlySold": 540,
    "categoryTree": [{"name": "Sports"}, {"name": "Water Bottles"}],
    "stats": {"buyBoxPrice": 2499, "current": [2599], "offerCountFBA": 6},
}


class KeepaMappingTests(unittest.TestCase):
    def test_sell_price_prefers_buybox_in_dollars(self):
        self.assertEqual(keepa_sell_price(KEEPA_OBJ), 24.99)

    def test_monthly_sales(self):
        self.assertEqual(keepa_monthly_sales(KEEPA_OBJ), 540)

    def test_competition_scales_with_offers(self):
        self.assertAlmostEqual(keepa_competition(KEEPA_OBJ), 0.30)

    def test_to_product_combines_live_data_with_your_cost(self):
        p = to_product(KEEPA_OBJ, cost=6.50, fulfilment=5)
        self.assertEqual(p.id, "B0EXAMPLE01")
        self.assertEqual(p.sell, 24.99)
        self.assertEqual(p.cost, 6.50)
        self.assertEqual(p.monthly_sales, 540)
        self.assertEqual(p.category, "water bottles")
        self.assertFalse(p.is_apparel)

    def test_missing_price_is_zero_not_crash(self):
        self.assertEqual(keepa_sell_price({"stats": {"buyBoxPrice": -1, "current": [-1]}}), 0.0)

    def test_load_asin_costs(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as fh:
            fh.write("asin,cost,fulfilment\nB01,5.0,4\nB02,9.5,\n")
        try:
            rows = load_asin_costs(path)
            self.assertEqual(rows[0], ("B01", 5.0, 4.0))
            self.assertEqual(rows[1], ("B02", 9.5, 4.0))   # blank fulfilment -> default
        finally:
            os.remove(path)


class SpApiMappingTests(unittest.TestCase):
    def test_inventory_to_stock(self):
        summaries = [
            {"sellerSku": "TEE-S-BLK", "totalQuantity": 15},
            {"sellerSku": "TEE-L-BLK", "totalQuantity": 0},
        ]
        self.assertEqual(inventory_to_stock(summaries), {"TEE-S-BLK": 15, "TEE-L-BLK": 0})


if __name__ == "__main__":
    unittest.main()
