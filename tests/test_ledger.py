import os
import tempfile
import time
import unittest

from ebe.store import Store
from ebe import ledger, subscriptions as subm


class LedgerTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "CUPS", "name": "Cups", "cost": 0.2, "sell": 0,
                                 "lead_time_days": 20, "on_hand": 5, "monthly_sales": 1000,
                                 "supplier": "Imports"}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_reconcile_mirrors_open_pos_into_payables_idempotently(self):
        self.s.create_po("CUPS", 1000, 0.2, supplier="Imports")
        self.assertEqual(ledger.reconcile(self.s), 1)
        self.assertEqual(ledger.reconcile(self.s), 0)         # idempotent — no duplicate
        ap = self.s.invoices(kind="AP")
        self.assertEqual(len(ap), 1)
        self.assertEqual(ap[0]["amount"], 200.0)

    def test_receivable_invoice_is_idempotent_by_ref(self):
        i1 = self.s.create_invoice("Cloud9", 1800, kind="AR", ref="sub:1:100")
        i2 = self.s.create_invoice("Cloud9", 1800, kind="AR", ref="sub:1:100")  # same occurrence
        self.assertIsNotNone(i1)
        self.assertIsNone(i2)
        self.assertEqual(len(self.s.invoices(kind="AR")), 1)

    def test_summarize_nets_ar_minus_ap(self):
        self.s.create_invoice("Cloud9", 1800, kind="AR", ref="ar1")
        self.s.create_po("CUPS", 1000, 0.2, supplier="Imports")
        ledger.reconcile(self.s)
        summ = ledger.summarize(self.s)
        self.assertEqual(summ["ar"], 1800.0)
        self.assertEqual(summ["ap"], 200.0)
        self.assertEqual(summ["net"], 1600.0)

    def test_overdue_flagged_by_due_date(self):
        self.s.create_invoice("LateCo", 500, kind="AR", due_days=-3, ref="late")
        summ = ledger.summarize(self.s)
        self.assertEqual(summ["overdue_total"], 500.0)

    def test_mark_paid_drops_from_open(self):
        iid = self.s.create_invoice("Cloud9", 1800, kind="AR", ref="ar2")
        self.s.mark_invoice_paid(iid)
        self.assertEqual(self.s.invoices(status="open"), [])

    def test_sell_subscription_opens_a_receivable(self):
        past = time.time() - 86400
        self.s.add_subscription("CUPS", 1000, 30, kind="sell", counterparty="Skyline",
                                unit_price=0.45, next_due=past)
        subm.run_due(self.s)
        ar = self.s.invoices(kind="AR")
        self.assertEqual(len(ar), 1)
        self.assertEqual(ar[0]["party"], "Skyline")
        self.assertEqual(ar[0]["amount"], 450.0)


if __name__ == "__main__":
    unittest.main()
