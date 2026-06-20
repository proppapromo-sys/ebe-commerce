import os
import tempfile
import unittest

from ebe.store import Store
from ebe import storefront


class StorefrontTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "CHARCOAL", "name": "Coconut charcoal", "category": "hookah",
             "cost": 6.0, "sell": 0, "on_hand": 50, "monthly_sales": 100},     # sell=0 → markup
            {"sku": "CUPS", "name": "To-go cups", "category": "supply",
             "cost": 0.2, "sell": 0.45, "on_hand": 500, "monthly_sales": 1000},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_b2b_price_uses_sell_or_marks_up_cost(self):
        self.assertEqual(storefront.b2b_price({"sell": 0.45, "cost": 0.2}), 0.45)
        self.assertEqual(storefront.b2b_price({"sell": 0, "cost": 6.0}), 8.40)   # cost×1.4

    def test_catalog_lists_supply_items(self):
        page = storefront.render_catalog(self.s)
        self.assertIn("EBE&nbsp;SUPPLY", page)
        self.assertIn("Coconut charcoal", page)
        self.assertIn("To-go cups", page)
        self.assertIn("action='/subscribe'", page)
        self.assertNotIn("<script", page.lower())          # static, no injected scripts

    def test_subscribe_creates_customer_and_subscription(self):
        sid = storefront.subscribe(self.s, "Cloud9 Lounge", "ap@c9.test",
                                   "CHARCOAL", 200, 14, 8.40)
        self.assertIsNotNone(sid)
        self.assertEqual(self.s.customer("Cloud9 Lounge")["email"], "ap@c9.test")
        sub = self.s.subscriptions()[0]
        self.assertEqual(sub["kind"], "sell")
        self.assertEqual(sub["counterparty"], "Cloud9 Lounge")
        self.assertEqual(sub["qty"], 200)
        self.assertEqual(sub["cadence_days"], 14)

    def test_subscribe_rejects_unknown_sku_or_blank_venue(self):
        self.assertIsNone(storefront.subscribe(self.s, "", "x", "CHARCOAL", 1, 7, 8.4))
        self.assertIsNone(storefront.subscribe(self.s, "V", "x", "NOPE", 1, 7, 8.4))

    def test_signup_flows_into_mrr(self):
        from ebe import subscriptions as subm
        storefront.subscribe(self.s, "Cloud9", "x", "CUPS", 1000, 30, 0.45)
        self.assertGreater(subm.summarize(self.s)["mrr_sell"], 0)   # storefront → MRR


if __name__ == "__main__":
    unittest.main()
