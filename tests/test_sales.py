import os
import tempfile
import unittest

from ebe.store import Store
from ebe.sales import pull_orders


class FakeShopify:
    def __init__(self, orders):
        self._orders = orders
    def orders(self, days=30, **kw):
        return self._orders


class SalesTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 50, "monthly_sales": 5},
            {"sku": "B", "name": "Beta", "cost": 3, "sell": 15, "on_hand": 20, "monthly_sales": 5},
        ])
        self.orders = [
            {"id": 1001, "line_items": [{"sku": "A", "quantity": 2, "price": "10.00"},
                                        {"sku": "B", "quantity": 1, "price": "15.00"}]},
            {"id": 1002, "line_items": [{"sku": "A", "quantity": 3, "price": "10.00"}]},
        ]

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_records_units_and_revenue(self):
        res = pull_orders(self.s, FakeShopify(self.orders))
        self.assertEqual(res["orders"], 2)
        self.assertEqual(res["units"], 6)               # 2+1+3
        self.assertEqual(res["revenue"], 65.0)          # 20 + 15 + 30
        self.assertEqual(res["by_sku"], {"A": 5, "B": 1})

    def test_decrements_on_hand(self):
        pull_orders(self.s, FakeShopify(self.orders))
        self.assertEqual(self.s.product("A")["on_hand"], 45)   # 50 - 5
        self.assertEqual(self.s.product("B")["on_hand"], 19)   # 20 - 1

    def test_idempotent_second_pull_records_nothing(self):
        pull_orders(self.s, FakeShopify(self.orders))
        res2 = pull_orders(self.s, FakeShopify(self.orders))
        self.assertEqual(res2["orders"], 0)
        self.assertEqual(res2["units"], 0)
        self.assertEqual(self.s.product("A")["on_hand"], 45)   # unchanged

    def test_unknown_sku_counted_in_revenue_not_stock(self):
        orders = [{"id": 2001, "line_items": [{"sku": "ZZZ", "quantity": 4, "price": "5.00"}]}]
        res = pull_orders(self.s, FakeShopify(orders))
        self.assertIn("ZZZ", res["unknown"])
        self.assertEqual(res["units"], 0)               # not in catalog → no stock move
        self.assertEqual(res["revenue"], 20.0)          # still counted as revenue

    def test_skips_orders_without_id(self):
        res = pull_orders(self.s, FakeShopify([{"line_items": [{"sku": "A", "quantity": 1, "price": "10"}]}]))
        self.assertEqual(res["orders"], 0)


if __name__ == "__main__":
    unittest.main()
