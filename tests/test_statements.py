import os
import tempfile
import time
import unittest

from ebe.store import Store
from ebe import statements, subscriptions as subm


class StatementTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "CUPS", "name": "Cups", "cost": 0.2, "sell": 0,
                                 "on_hand": 100, "monthly_sales": 1000}])
        self.s.upsert_customers([{"name": "Cloud9", "email": "ap@c9.test", "terms_days": 7}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_customer_terms_drive_invoice_due_date(self):
        past = time.time() - 86400
        self.s.add_subscription("CUPS", 100, 30, kind="sell", counterparty="Cloud9",
                                unit_price=0.45, next_due=past)
        subm.run_due(self.s)
        inv = self.s.invoices(kind="AR")[0]
        # net-7 terms → due ~7 days out, well under the default 14
        self.assertLess(inv["due_at"] - time.time(), 7.5 * 86400)

    def test_statement_lists_balance_and_total(self):
        self.s.create_invoice("Cloud9", 1800, kind="AR", ref="a1", memo="weekly supply")
        self.s.create_invoice("Cloud9", 450, kind="AR", ref="a2", memo="extra")
        doc = statements.statement(self.s, "Cloud9")
        self.assertIn("Statement · Cloud9", doc)
        self.assertIn("ap@c9.test", doc)              # contact pulled from customer record
        self.assertIn("net 7 days", doc)
        self.assertIn("$2250.00", doc)                # total due

    def test_overdue_is_flagged(self):
        self.s.create_invoice("Cloud9", 500, kind="AR", due_days=-2, ref="late")
        self.assertIn("overdue", statements.statement(self.s, "Cloud9").lower())

    def test_all_statements_grand_total(self):
        self.s.create_invoice("Cloud9", 1000, kind="AR", ref="x1")
        self.s.create_invoice("Skyline", 250, kind="AR", ref="x2")
        doc = statements.all_statements(self.s)
        self.assertIn("TOTAL OUTSTANDING (all customers): $1250.00", doc)
        self.assertIn("2 customer(s)", doc)

    def test_no_balance_is_clean(self):
        self.assertIn("No open receivables", statements.all_statements(self.s))


if __name__ == "__main__":
    unittest.main()
