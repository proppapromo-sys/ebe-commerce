import os
import tempfile
import unittest

from ebe.store import Store
from ebe import bundles as bmod
from ebe.fees import SHOPIFY


class BundleTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "HMD", "name": "Holder", "cost": 1.50, "sell": 12.99, "on_hand": 100, "monthly_sales": 50},
            {"sku": "COAL", "name": "Charcoal", "cost": 3.00, "sell": 14.99, "on_hand": 100, "monthly_sales": 1000},
            {"sku": "TIPS", "name": "Tips", "cost": 1.30, "sell": 5.49, "on_hand": 100, "monthly_sales": 200},
        ])
        self.s.define_bundle("KIT", "Starter Kit", 29.99,
                             [("HMD", 1), ("COAL", 1), ("TIPS", 2)])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_bundle_cost_is_sum_of_parts(self):
        self.assertEqual(self.s.bundle_cost("KIT"), round(1.50 + 3.00 + 2 * 1.30, 2))  # 7.10

    def test_bundle_margin_beats_a_cheap_component(self):
        kit = bmod.margins(self.s, "KIT", SHOPIFY)
        self.assertEqual(kit["cost"], 7.10)
        self.assertGreater(kit["margin"], 0.30)        # 29.99 kit is a healthy margin

    def test_selling_a_bundle_draws_down_each_component(self):
        self.s.sell_bundle("KIT", 5)
        self.assertEqual(self.s.product("HMD")["on_hand"], 95)    # 1×5
        self.assertEqual(self.s.product("COAL")["on_hand"], 95)   # 1×5
        self.assertEqual(self.s.product("TIPS")["on_hand"], 90)   # 2×5

    def test_load_from_csv_roundtrips(self):
        fd, p = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("bundle_sku,name,price,component_sku,qty\n")
                fh.write("K2,Combo,19.99,HMD,1\nK2,Combo,19.99,COAL,1\n")
            n = bmod.load_into_store(self.s, p)
            self.assertEqual(n, 1)
            self.assertEqual(self.s.bundle("K2")["cost"], 4.50)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
