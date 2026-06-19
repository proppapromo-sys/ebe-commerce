import os
import tempfile
import unittest

from ebe.costs import load_cost_sheet, apply_costs, apply_stock
from ebe.catalog.product import Product, Variant


class CostSheetTests(unittest.TestCase):
    def test_load_and_apply(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as fh:
            fh.write("sku,cost,fulfilment\nP1,4.10,4\nM1,7.80,\n")
        try:
            sheet = load_cost_sheet(path)
            self.assertEqual(sheet["P1"], {"cost": 4.10, "fulfilment": 4.0})
            self.assertEqual(sheet["M1"], {"cost": 7.80})       # blank fulfilment -> not overridden
            prods = [Product("P1", "x", "home", cost=9, sell=22, fulfilment=9),
                     Product("M1", "tee", "apparel", cost=12, sell=28, fulfilment=6)]
            apply_costs(prods, sheet)
            self.assertEqual(prods[0].cost, 4.10)
            self.assertEqual(prods[0].fulfilment, 4.0)
            self.assertEqual(prods[1].cost, 7.80)
            self.assertEqual(prods[1].fulfilment, 6)             # untouched (no value in sheet)
        finally:
            os.remove(path)

    def test_unmatched_sku_left_alone(self):
        prods = [Product("Z", "z", "home", cost=5, sell=20)]
        apply_costs(prods, {"OTHER": {"cost": 1}})
        self.assertEqual(prods[0].cost, 5)


class StockOverlayTests(unittest.TestCase):
    def test_simple_and_variant_stock(self):
        prods = [
            Product("P1", "x", "home", cost=5, sell=20, on_hand=0),
            Product("M1", "tee", "apparel", cost=9, sell=28,
                    variants=[Variant("S", "Black", on_hand=0), Variant("L", "Black", on_hand=0)]),
        ]
        apply_stock(prods, {"P1": 900, "M1·S/Black": 15, "M1·L/Black": 8})
        self.assertEqual(prods[0].on_hand, 900)
        self.assertEqual(prods[1].variants[0].on_hand, 15)
        self.assertEqual(prods[1].variants[1].on_hand, 8)


if __name__ == "__main__":
    unittest.main()
