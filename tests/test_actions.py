import os
import tempfile
import time
import unittest

from ebe.store import Store
from ebe import actions


class ActionTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "CAP", "name": "Cap", "cost": 7, "sell": 24,
                                 "lead_time_days": 25, "on_hand": 4, "monthly_sales": 150,
                                 "supplier": "Mill"}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_propose_lists_rebuy_with_impact(self):
        acts = actions.propose(self.s)
        self.assertTrue(any(a["id"] == "po:CAP" for a in acts))
        po = next(a for a in acts if a["id"] == "po:CAP")
        self.assertEqual(po["flow"], "out")
        self.assertGreater(po["impact"], 0)

    def test_propose_is_read_only(self):
        actions.propose(self.s)
        self.assertEqual(self.s.purchase_orders("draft"), [])   # nothing raised by proposing

    def test_execute_raises_the_approved_po(self):
        res = actions.execute(self.s, ["po:CAP"])
        self.assertTrue(res[0]["ok"])
        self.assertEqual(len(self.s.purchase_orders("draft")), 1)

    def test_execute_only_approved_ids(self):
        # a due sell-subscription is proposed but we approve ONLY the PO
        self.s.add_subscription("CAP", 100, 7, kind="sell", counterparty="LoungeX",
                                unit_price=12, next_due=time.time() - 86400)
        acts = actions.propose(self.s)
        self.assertTrue(any(a["id"].startswith("sub:") for a in acts))
        actions.execute(self.s, ["po:CAP"])                    # approve PO only
        self.assertEqual(self.s.invoices(kind="AR"), [])       # sub NOT billed (not approved)

    def test_summarize_splits_in_and_out(self):
        self.s.add_subscription("CAP", 100, 30, kind="sell", counterparty="LoungeX",
                                unit_price=12, next_due=time.time() - 86400)
        summ = actions.summarize(actions.propose(self.s))
        self.assertGreater(summ["cash_out"], 0)                # the PO
        self.assertEqual(summ["cash_in"], 1200.0)              # the sell sub (100 × $12)


if __name__ == "__main__":
    unittest.main()
