import os
import tempfile
import unittest

from ebe.store import Store
from ebe import sync
from ebe.adapters import config


class ShopifyStub:
    def stock(self):
        return {"A": 4}
    def prices(self, skus=None):
        return [{"sku": "A", "price": 22.0}]


class SyncAllTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "A", "name": "thing", "cost": 5, "sell": 20,
                                 "on_hand": 999, "monthly_sales": 50}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_configured_channels_reads_env(self):
        config._LOADED = True
        for k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID",
                  "SHOPIFY_CLIENT_SECRET", "SPAPI_REFRESH_TOKEN",
                  "SPAPI_CLIENT_ID", "SPAPI_CLIENT_SECRET"):
            os.environ.pop(k, None)
        self.assertEqual(sync.configured_channels(), [])           # nothing set → none
        os.environ["SHOPIFY_STORE"] = "g0zjm0-ew"
        os.environ["SHOPIFY_CLIENT_ID"] = "cid"
        os.environ["SHOPIFY_CLIENT_SECRET"] = "secret"
        try:
            self.assertIn("shopify", sync.configured_channels())
            self.assertNotIn("amazon", sync.configured_channels())
        finally:
            for k in ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
                os.environ.pop(k, None)

    def test_sync_all_skips_unconfigured_and_runs_configured(self):
        # monkeypatch the channel factory so no network is touched
        orig = sync.channel_client
        sync.channel_client = lambda name, region="na", marketplace="us": ShopifyStub()
        orig_chans = sync.configured_channels
        sync.configured_channels = lambda: ["shopify"]
        try:
            res = sync.sync_all(self.s)
            self.assertIn("shopify", res)
            self.assertEqual(self.s.product("A")["on_hand"], 4)     # 999 → live 4
        finally:
            sync.channel_client = orig
            sync.configured_channels = orig_chans

    def test_sync_all_records_per_channel_error(self):
        def boom(name, region="na", marketplace="us"):
            raise RuntimeError("no creds")
        sync.channel_client = boom
        sync.configured_channels = lambda: ["amazon"]
        try:
            res = sync.sync_all(self.s)
            self.assertIn("error", res["amazon"])
        finally:
            import importlib
            importlib.reload(sync)


if __name__ == "__main__":
    unittest.main()
