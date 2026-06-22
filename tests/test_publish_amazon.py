import os
import tempfile
import unittest

from ebe.store import Store
from ebe.publish import publish_to_amazon, amazon_attributes, _plain


class FakeSpApi:
    def __init__(self, fail_skus=()):
        self.calls = []
        self.fail = set(fail_skus)
    def put_listing(self, seller_id, sku, product_type, attributes, requirements="LISTING"):
        if sku in self.fail:
            raise RuntimeError("invalid attributes")
        self.calls.append({"seller_id": seller_id, "sku": sku,
                           "product_type": product_type, "attributes": attributes})
        return {"sku": sku, "status": "ACCEPTED"}


class AmazonAttrTests(unittest.TestCase):
    def test_plain_strips_html(self):
        self.assertEqual(_plain("<p>Hi <b>there</b></p>"), "Hi there")

    def test_attributes_shape(self):
        p = {"sku": "A", "name": "Alpha", "sell": 14.99, "on_hand": 12,
             "description": "<p>Great</p>", "supplier": "Acme"}
        a = amazon_attributes(p, "ATVPDKIKX0DER")
        self.assertEqual(a["item_name"][0]["value"], "Alpha")
        self.assertEqual(a["brand"][0]["value"], "Acme")
        self.assertEqual(a["product_description"][0]["value"], "Great")   # html stripped
        self.assertEqual(a["fulfillment_availability"][0]["quantity"], 12)
        self.assertEqual(a["purchasable_offer"][0]["our_price"][0]["schedule"][0]["value_with_tax"], 14.99)
        self.assertEqual(a["condition_type"][0]["value"], "new_new")


class PublishToAmazonTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 5},
            {"sku": "B", "name": "Beta", "cost": 3, "sell": 15, "on_hand": 0},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_submits_all(self):
        api = FakeSpApi()
        res = publish_to_amazon(self.s, api, "SELLER1", "PRODUCT", "ATVPDKIKX0DER")
        self.assertEqual(set(res["created"]), {"A", "B"})
        self.assertEqual(len(api.calls), 2)
        self.assertEqual(api.calls[0]["seller_id"], "SELLER1")
        self.assertEqual(api.calls[0]["product_type"], "PRODUCT")

    def test_only_filter(self):
        api = FakeSpApi()
        res = publish_to_amazon(self.s, api, "S", "PRODUCT", "MP", only=["B"])
        self.assertEqual(res["created"], ["B"])
        self.assertEqual(len(api.calls), 1)

    def test_failure_captured(self):
        api = FakeSpApi(fail_skus=["A"])
        res = publish_to_amazon(self.s, api, "S", "PRODUCT", "MP")
        self.assertEqual(res["created"], ["B"])
        self.assertEqual(res["failed"][0][0], "A")
        self.assertIn("invalid attributes", res["failed"][0][1])


if __name__ == "__main__":
    unittest.main()
