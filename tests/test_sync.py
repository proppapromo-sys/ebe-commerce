import os
import tempfile
import unittest

from ebe.store import Store
from ebe.sync import sync_stock
from ebe import autobuy


class StubSpApi:
    """Stands in for SpApiClient — returns canned SP-API shapes, no network."""
    def __init__(self, summaries, prices=None):
        self._summaries = summaries
        self._prices = prices or []
    def fba_inventory(self):
        return self._summaries
    def my_price(self, skus):
        return [r for r in self._prices if r.get("SellerSKU") in skus]


class SyncTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "M2-Navy", "name": "Cap Navy", "cost": 7, "sell": 24,
             "lead_time_days": 25, "on_hand": 999, "monthly_sales": 150},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_live_stock_overwrites_typed_stock(self):
        client = StubSpApi([{"sellerSku": "M2-Navy", "totalQuantity": 4}])
        res = sync_stock(self.s, client)
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 4)   # 999 → live 4
        self.assertEqual(res["updated"], [("M2-Navy", 4)])

    def test_unknown_sku_is_reported_not_created(self):
        client = StubSpApi([{"sellerSku": "GHOST", "totalQuantity": 10}])
        res = sync_stock(self.s, client)
        self.assertIn("GHOST", res["unknown"])
        self.assertIsNone(self.s.product("GHOST"))

    def test_synced_low_stock_then_rebuy_fires(self):
        # before sync the SKU is well stocked → no reorder
        self.assertEqual(autobuy.plan(self.s), [])
        sync_stock(self.s, StubSpApi([{"sellerSku": "M2-Navy", "totalQuantity": 4}]))
        # live truth says nearly out → engine now proposes a buy
        self.assertEqual([p["sku"] for p in autobuy.plan(self.s)], ["M2-Navy"])

    def test_prices_pulled_when_requested(self):
        client = StubSpApi(
            [{"sellerSku": "M2-Navy", "totalQuantity": 50}],
            prices=[{"SellerSKU": "M2-Navy", "Product": {"Offers": [
                {"BuyingPrice": {"ListingPrice": {"Amount": 26.5}}}]}}])
        res = sync_stock(self.s, client, prices=True)
        self.assertEqual(self.s.product("M2-Navy")["sell"], 26.5)
        self.assertEqual(res["priced"], [("M2-Navy", 26.5)])


if __name__ == "__main__":
    unittest.main()
