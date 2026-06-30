import unittest

from ebe.adapters.amazon_spapi import product_types_from_payload, SpApiClient


class ProductTypesParseTests(unittest.TestCase):
    def test_parse_payload(self):
        data = {"productTypes": [
            {"name": "CHARCOAL", "displayName": "Charcoal & Briquettes"},
            {"name": "PRODUCT"},                       # no displayName -> falls back to name
        ]}
        out = product_types_from_payload(data)
        self.assertEqual(out[0], {"name": "CHARCOAL", "displayName": "Charcoal & Briquettes"})
        self.assertEqual(out[1], {"name": "PRODUCT", "displayName": "PRODUCT"})

    def test_parse_empty(self):
        self.assertEqual(product_types_from_payload({}), [])
        self.assertEqual(product_types_from_payload({"productTypes": []}), [])

    def test_search_calls_definitions_endpoint(self):
        c = SpApiClient(refresh_token="r", client_id="c", client_secret="s")
        seen = {}
        def fake_get(path, params=None):
            seen["path"], seen["params"] = path, params
            return {"productTypes": [{"name": "CHAIR", "displayName": "Chair"}]}
        c._get = fake_get
        out = c.search_product_types("chair")
        self.assertEqual(out[0]["name"], "CHAIR")
        self.assertIn("/definitions/2020-09-01/productTypes", seen["path"])
        self.assertEqual(seen["params"]["keywords"], "chair")
        self.assertIn("marketplaceIds", seen["params"])


if __name__ == "__main__":
    unittest.main()
