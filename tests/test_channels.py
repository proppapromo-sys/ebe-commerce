import os
import tempfile
import unittest

from ebe.store import Store
from ebe.sync import sync_stock
from ebe.adapters.shopify import variants_to_stock
from ebe.adapters.square import orders_to_counts


class ShopifyStub:
    """Implements the generic channel interface (stock/prices), no network."""
    def __init__(self, variants):
        self._v = variants
    def stock(self):
        return variants_to_stock(self._v)
    def prices(self, skus=None):
        return [{"sku": v["sku"], "price": float(v["price"])}
                for v in self._v if v.get("sku") and (skus is None or v["sku"] in skus)]


class ChannelSyncTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "TEE-BLK-L", "name": "Tee L", "cost": 9, "sell": 28,
             "lead_time_days": 21, "on_hand": 999, "monthly_sales": 90},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_shopify_variants_map_to_stock(self):
        v = [{"sku": "TEE-BLK-L", "inventory_quantity": 4, "price": "28.00"},
             {"sku": "", "inventory_quantity": 5, "price": "0"}]   # blank sku ignored
        self.assertEqual(variants_to_stock(v), {"TEE-BLK-L": 4})

    def test_sync_uses_generic_stock_interface(self):
        client = ShopifyStub([{"sku": "TEE-BLK-L", "inventory_quantity": 3, "price": "30.00"}])
        res = sync_stock(self.s, client, prices=True)
        self.assertEqual(self.s.product("TEE-BLK-L")["on_hand"], 3)   # 999 → live 3
        self.assertEqual(self.s.product("TEE-BLK-L")["sell"], 30.0)   # generic prices() path
        self.assertEqual(res["updated"], [("TEE-BLK-L", 3)])

    def test_square_orders_aggregate_by_item(self):
        orders = [
            {"line_items": [{"name": "Hookah", "quantity": "2"}, {"name": "Drink", "quantity": "3"}]},
            {"line_items": [{"name": "Hookah", "quantity": "1"}]},
        ]
        self.assertEqual(orders_to_counts(orders), {"Hookah": 3, "Drink": 3})


class IntegrationRegistryTests(unittest.TestCase):
    def test_needs_is_derived_from_live_integrations(self):
        from ebe.adapters import config
        self.assertIn("shopify", config.NEEDS)            # new live channel present
        self.assertIn("square", config.NEEDS)
        self.assertNotIn("printful", config.NEEDS)        # planned, not validated by the doctor
        # every live integration carries a signup URL + role for the connections map
        for name, keys in config.NEEDS.items():
            meta = config.INTEGRATIONS[name]
            self.assertTrue(meta["signup"].startswith("http"))
            self.assertTrue(meta["role"])


if __name__ == "__main__":
    unittest.main()
