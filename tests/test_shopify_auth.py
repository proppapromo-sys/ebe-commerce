import os
import tempfile
import unittest

from ebe.adapters import shopify_auth, config


class ShopifyAuthTests(unittest.TestCase):
    def test_build_auth_url_has_all_oauth_params(self):
        url = shopify_auth.build_auth_url("g0zjm0-ew", "abc123", "state42")
        self.assertIn("https://g0zjm0-ew.myshopify.com/admin/oauth/authorize", url)
        self.assertIn("client_id=abc123", url)
        self.assertIn("scope=read_products", url)
        self.assertIn("state=state42", url)
        self.assertIn("localhost%3A8723%2Fcallback", url)   # redirect is url-encoded

    def test_exchange_code_pulls_access_token(self):
        # patch request_json so no network is touched
        calls = {}

        def fake_request_json(method, url, **kw):
            calls["url"] = url
            calls["body"] = kw.get("json_body")
            return {"access_token": "shpat_live_token", "scope": "read_products"}

        orig = shopify_auth.request_json
        shopify_auth.request_json = fake_request_json
        try:
            tok = shopify_auth.exchange_code("g0zjm0-ew", "cid", "secret", "thecode")
            self.assertEqual(tok, "shpat_live_token")
            self.assertIn("/admin/oauth/access_token", calls["url"])
            self.assertEqual(calls["body"]["code"], "thecode")
        finally:
            shopify_auth.request_json = orig


class SetEnvTests(unittest.TestCase):
    def test_set_env_upserts_key(self):
        fd, path = tempfile.mkstemp(suffix=".env")
        os.close(fd)
        try:
            with open(path, "w") as fh:
                fh.write("SHOPIFY_STORE=g0zjm0-ew\nSHOPIFY_TOKEN=old\n")
            config.set_env("SHOPIFY_TOKEN", "newtoken", path=path)
            config.set_env("FRESH_KEY", "v", path=path)
            body = open(path).read()
            self.assertIn("SHOPIFY_TOKEN=newtoken", body)
            self.assertNotIn("SHOPIFY_TOKEN=old", body)
            self.assertIn("FRESH_KEY=v", body)
            self.assertEqual(body.count("SHOPIFY_TOKEN="), 1)   # upsert, not duplicate
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
