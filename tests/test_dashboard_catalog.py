import os
import tempfile
import types
import unittest

from ebe import dashboard as d
from ebe.store import Store


class DashboardCatalogTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.a = types.SimpleNamespace(profile="generic", fees="amazon-fba",
                                       capital=None, db=self.path)

    def tearDown(self):
        os.remove(self.path)

    def test_render_lists_products(self):
        s = Store(self.path)
        s.upsert_products([{"sku": "A", "name": "Alpha", "cost": 2, "sell": 10,
                            "on_hand": 5, "monthly_sales": 9}])
        s.close()
        html = d.render_catalog(self.a, "")
        self.assertIn("Catalog", html)
        self.assertIn("Alpha", html)
        self.assertIn("/catalog-add", html)        # the add form is present

    def test_add_handler_creates(self):
        msg = d._do_catalog_add(self.a, {"sku": ["B"], "name": ["Beta"],
                                         "cost": ["3"], "sell": ["12"]})
        self.assertIn("added", msg)
        s = Store(self.path)
        p = s.product("B")
        s.close()
        self.assertEqual(p["name"], "Beta")
        self.assertEqual(p["sell"], 12.0)

    def test_add_handler_partial_update_preserves_name(self):
        d._do_catalog_add(self.a, {"sku": ["B"], "name": ["Beta"], "sell": ["12"]})
        msg = d._do_catalog_add(self.a, {"sku": ["B"], "sell": ["15"]})
        self.assertIn("updated", msg)
        s = Store(self.path)
        p = s.product("B")
        s.close()
        self.assertEqual(p["sell"], 15.0)
        self.assertEqual(p["name"], "Beta")        # untouched

    def test_add_requires_sku(self):
        msg = d._do_catalog_add(self.a, {"name": ["No SKU"]})
        self.assertTrue(msg.startswith("✕"))

    def test_publish_failure_is_reported_not_raised(self):
        # no Shopify creds in env → ShopifyClient construction fails; handler returns a msg
        for k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
            os.environ.pop(k, None)
        from ebe.adapters import config
        config._LOADED = True
        msg = d._do_catalog_publish(self.a)
        self.assertTrue(msg.startswith("✕"))


if __name__ == "__main__":
    unittest.main()
