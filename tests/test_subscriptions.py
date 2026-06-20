import os
import tempfile
import time
import unittest

from ebe.store import Store
from ebe import subscriptions as subm


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "CHARCOAL", "name": "Charcoal", "cost": 10,
                                 "sell": 0, "on_hand": 50, "monthly_sales": 100}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_mrr_normalises_cadence_to_30_days(self):
        # weekly sell of 150 @ $12 → 150*12*30/7 ≈ $7,714/mo
        self.s.add_subscription("CHARCOAL", 150, 7, kind="sell", counterparty="Lounge", unit_price=12.0)
        summ = subm.summarize(self.s)
        self.assertAlmostEqual(summ["mrr_sell"], round(150 * 12 * 30 / 7, 2), places=2)
        self.assertEqual(summ["mrr_buy"], 0.0)

    def test_due_only_when_next_due_passed(self):
        future = time.time() + 5 * 86400
        self.s.add_subscription("CHARCOAL", 10, 14, kind="buy", next_due=future)
        self.assertEqual(self.s.due_subscriptions(), [])           # not due yet
        self.assertEqual(len(self.s.due_subscriptions(future + 1)), 1)

    def test_run_due_buy_raises_po_and_rolls_forward(self):
        past = time.time() - 86400
        self.s.upsert_offers([{"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 6.0, "min_qty": 1}])
        sid = self.s.add_subscription("CHARCOAL", 100, 14, kind="buy",
                                      counterparty="Default", unit_price=7.0, next_due=past)
        actioned = subm.run_due(self.s)
        self.assertEqual(len(actioned), 1)
        po = self.s.purchase_orders("draft")[0]
        self.assertEqual(po["supplier"], "Cheap")                  # vendor auction applied
        self.assertEqual(po["unit_cost"], 6.0)
        # rolled forward → no longer due
        self.assertEqual(self.s.due_subscriptions(), [])

    def test_run_due_sell_books_revenue_event(self):
        past = time.time() - 86400
        self.s.add_subscription("CHARCOAL", 150, 7, kind="sell",
                                counterparty="Lounge", unit_price=12.0, next_due=past)
        actioned = subm.run_due(self.s)
        self.assertEqual(actioned[0]["kind"], "sell")
        self.assertEqual(actioned[0]["revenue"], 1800.0)
        kinds = [e["kind"] for e in self.s.events()]
        self.assertIn("subscription_sell", kinds)


if __name__ == "__main__":
    unittest.main()
