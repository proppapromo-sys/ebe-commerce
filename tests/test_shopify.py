import os
import unittest

from ebe.adapters import shopify, config


class ShopifyClientCredentialsTests(unittest.TestCase):
    def setUp(self):
        config._LOADED = True
        for k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
            os.environ.pop(k, None)
        self._orig = shopify.request_json

    def tearDown(self):
        shopify.request_json = self._orig
        for k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
            os.environ.pop(k, None)

    def test_mint_access_token_calls_oauth_endpoint(self):
        seen = {}

        def fake(method, url, **kw):
            seen["method"], seen["url"], seen["body"] = method, url, kw.get("json_body")
            return {"access_token": "shpat_minted", "expires_in": 86399}

        shopify.request_json = fake
        token, ttl = shopify.mint_access_token("g0zjm0-ew", "cid", "secret")
        self.assertEqual(token, "shpat_minted")
        self.assertEqual(ttl, 86399)
        self.assertEqual(seen["method"], "POST")
        self.assertIn("/admin/oauth/access_token", seen["url"])
        self.assertEqual(seen["body"]["grant_type"], "client_credentials")
        self.assertEqual(seen["body"]["client_id"], "cid")

    def test_client_prefers_client_credentials_over_static_token(self):
        # even a (bad) static token present, client mints from id+secret
        os.environ["SHOPIFY_STORE"] = "g0zjm0-ew"
        os.environ["SHOPIFY_TOKEN"] = "bad_automation_token"
        os.environ["SHOPIFY_CLIENT_ID"] = "cid"
        os.environ["SHOPIFY_CLIENT_SECRET"] = "secret"
        shopify.request_json = lambda *a, **k: {"access_token": "shpat_minted", "expires_in": 86399}
        c = shopify.ShopifyClient()
        self.assertEqual(c.token, "shpat_minted")

    def test_client_falls_back_to_static_token(self):
        os.environ["SHOPIFY_STORE"] = "g0zjm0-ew"
        os.environ["SHOPIFY_TOKEN"] = "shpat_legacy"
        # no client id/secret → use the static token, mint never called
        def boom(*a, **k):
            raise AssertionError("should not mint when only a static token is set")
        shopify.request_json = boom
        c = shopify.ShopifyClient()
        self.assertEqual(c.token, "shpat_legacy")

    def test_missing_everything_raises(self):
        os.environ["SHOPIFY_STORE"] = "g0zjm0-ew"
        from ebe.adapters.base import AdapterError
        with self.assertRaises(AdapterError):
            shopify.ShopifyClient()


if __name__ == "__main__":
    unittest.main()
