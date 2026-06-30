import os
import unittest

from ebe.adapters import ebay, config
from ebe import sync


class EbayStockMapTests(unittest.TestCase):
    def test_inventory_to_stock(self):
        items = [
            {"sku": "A", "availability": {"shipToLocationAvailability": {"quantity": 7}}},
            {"sku": "B", "availability": {"shipToLocationAvailability": {"quantity": 0}}},
            {"sku": "C"},                                  # no availability -> 0
        ]
        self.assertEqual(ebay.inventory_to_stock(items), {"A": 7, "B": 0, "C": 0})


class EbayClientTests(unittest.TestCase):
    def setUp(self):
        for k in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_REFRESH_TOKEN"):
            os.environ.pop(k, None)
        self._orig = ebay.request_json

    def tearDown(self):
        ebay.request_json = self._orig
        for k in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_REFRESH_TOKEN"):
            os.environ.pop(k, None)

    def test_missing_creds_raises(self):
        from ebe.adapters.base import AdapterError
        with self.assertRaises(AdapterError):
            ebay.EbayClient()

    def test_token_then_stock(self):
        calls = []
        def fake(method, url, headers=None, params=None, form=None, **kw):
            calls.append(url)
            if "oauth2/token" in url:
                self.assertIn("Authorization", headers)            # Basic auth
                self.assertEqual(form["grant_type"], "refresh_token")
                return {"access_token": "AT", "expires_in": 7200}
            if "inventory_item" in url:
                self.assertEqual(headers["Authorization"], "Bearer AT")
                return {"inventoryItems": [
                    {"sku": "X", "availability": {"shipToLocationAvailability": {"quantity": 4}}}]}
            return {}
        ebay.request_json = fake
        c = ebay.EbayClient(client_id="id", client_secret="sec", refresh_token="rt")
        self.assertEqual(c.stock(), {"X": 4})
        self.assertTrue(any("oauth2/token" in u for u in calls))


class EbayInSyncTests(unittest.TestCase):
    def test_configured_channels_includes_ebay(self):
        config._LOADED = True
        for k in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_REFRESH_TOKEN",
                  "SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET",
                  "SPAPI_REFRESH_TOKEN", "SPAPI_CLIENT_ID", "SPAPI_CLIENT_SECRET"):
            os.environ.pop(k, None)
        self.assertNotIn("ebay", sync.configured_channels())
        os.environ["EBAY_CLIENT_ID"] = "id"
        os.environ["EBAY_CLIENT_SECRET"] = "sec"
        os.environ["EBAY_REFRESH_TOKEN"] = "rt"
        try:
            self.assertIn("ebay", sync.configured_channels())
        finally:
            for k in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_REFRESH_TOKEN"):
                os.environ.pop(k, None)


class BrandTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("EBE_BRAND", None)

    def test_default(self):
        from ebe import brand
        os.environ.pop("EBE_BRAND", None)
        self.assertEqual(brand.name(), "EBE OS")
        self.assertEqual(brand.upper(), "EBE OS")

    def test_override(self):
        from ebe import brand
        os.environ["EBE_BRAND"] = "EBE Command"
        self.assertEqual(brand.name(), "EBE Command")
        self.assertEqual(brand.upper(), "EBE COMMAND")


if __name__ == "__main__":
    unittest.main()
