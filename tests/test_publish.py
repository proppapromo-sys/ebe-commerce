import os
import tempfile
import unittest

from ebe.store import Store
from ebe.publish import publish_catalog


class FakeShopify:
    """Stand-in channel: records created products, reports existing variants."""
    def __init__(self, existing=()):
        self._existing = list(existing)
        self.created = []

    def variants(self):
        return [{"sku": s} for s in self._existing]

    def create_product(self, sku, title, price, body_html="", qty=None, status="active"):
        self.created.append({"sku": sku, "title": title, "price": price, "qty": qty})
        self._existing.append(sku)
        return {"product": {"variants": [{"sku": sku}]}}


class PublishTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "A", "name": "Alpha", "cost": 2, "sell": 10, "on_hand": 7, "monthly_sales": 5},
            {"sku": "B", "name": "Beta", "cost": 3, "sell": 15, "on_hand": 0, "monthly_sales": 5},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_creates_missing_only(self):
        chan = FakeShopify(existing=["A"])          # A already on Shopify
        res = publish_catalog(self.s, chan)
        self.assertEqual(res["created"], ["B"])
        self.assertEqual(res["skipped"], ["A"])
        self.assertEqual(len(chan.created), 1)
        self.assertEqual(chan.created[0]["sku"], "B")

    def test_untracked_by_default(self):
        chan = FakeShopify()
        publish_catalog(self.s, chan)
        self.assertTrue(all(c["qty"] is None for c in chan.created))   # listed, untracked

    def test_set_stock_pushes_on_hand(self):
        chan = FakeShopify()
        publish_catalog(self.s, chan, set_stock=True)
        byk = {c["sku"]: c for c in chan.created}
        self.assertEqual(byk["A"]["qty"], 7)
        self.assertEqual(byk["B"]["qty"], 0)

    def test_only_filter(self):
        chan = FakeShopify()
        res = publish_catalog(self.s, chan, only=["B"])
        self.assertEqual(res["created"], ["B"])
        self.assertNotIn("A", [c["sku"] for c in chan.created])

    def test_rerun_is_idempotent(self):
        chan = FakeShopify()
        publish_catalog(self.s, chan)               # creates A, B
        res2 = publish_catalog(self.s, chan)        # nothing new
        self.assertEqual(res2["created"], [])
        self.assertEqual(set(res2["skipped"]), {"A", "B"})

    def test_failure_is_captured(self):
        class Boom(FakeShopify):
            def create_product(self, **kw):
                raise RuntimeError("write_products scope missing")
        chan = Boom()
        res = publish_catalog(self.s, chan)
        self.assertEqual(res["created"], [])
        self.assertEqual(len(res["failed"]), 2)
        self.assertIn("write_products", res["failed"][0][1])


if __name__ == "__main__":
    unittest.main()
