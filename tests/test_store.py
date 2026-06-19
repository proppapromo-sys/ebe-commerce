import os
import tempfile
import unittest

from ebe.store import Store
from ebe import autobuy


def _rows():
    return [
        # a fast mover that's about to run dry → must reorder
        {"sku": "M2-Navy", "name": "Embroidered cap Navy", "category": "apparel",
         "cost": 7, "sell": 24, "lead_time_days": 25, "on_hand": 5, "monthly_sales": 150},
        # a well-stocked SKU → must NOT reorder
        {"sku": "P1", "name": "LED strip", "category": "home",
         "cost": 5, "sell": 22, "lead_time_days": 18, "on_hand": 900, "monthly_sales": 80},
    ]


class StoreTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_upsert_and_read_back(self):
        self.assertEqual(self.s.upsert_products(_rows()), 2)
        self.assertEqual(len(self.s.products()), 2)
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 5)

    def test_upsert_updates_not_duplicates(self):
        self.s.upsert_products(_rows())
        self.s.upsert_products([{"sku": "P1", "name": "LED strip", "on_hand": 50}])
        self.assertEqual(len(self.s.products()), 2)          # still 2, P1 updated
        self.assertEqual(self.s.product("P1")["on_hand"], 50)

    def test_record_sale_drops_stock_and_floors_at_zero(self):
        self.s.upsert_products(_rows())
        self.s.record_sale("M2-Navy", 3)
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 2)
        self.s.record_sale("M2-Navy", 100)                   # oversell
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 0)

    def test_receive_po_adds_units_and_closes(self):
        self.s.upsert_products(_rows())
        pid = self.s.create_po("M2-Navy", 200, 7, reason="restock")
        self.assertEqual(self.s.purchase_order(pid)["status"], "draft")
        self.s.receive_po(pid)
        self.assertEqual(self.s.purchase_order(pid)["status"], "received")
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 205)


class AutobuyTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products(_rows())

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_plan_flags_only_the_low_sku(self):
        skus = [p["sku"] for p in autobuy.plan(self.s)]
        self.assertIn("M2-Navy", skus)
        self.assertNotIn("P1", skus)

    def test_scan_raises_draft_pos_and_does_not_double_order(self):
        first = autobuy.scan(self.s)
        self.assertTrue(first)
        self.assertEqual(first[0]["status"], "draft")
        self.assertEqual(first[0]["sku"], "M2-Navy")
        # second scan must NOT raise another PO for the same in-flight SKU
        self.assertEqual(autobuy.scan(self.s), [])

    def test_auto_mode_marks_ordered(self):
        raised = autobuy.scan(self.s, auto=True)
        self.assertEqual(raised[0]["status"], "ordered")

    def test_budget_caps_cash(self):
        # tiny budget below the cap order's cash → nothing raised
        raised = autobuy.scan(self.s, budget=1.0)
        self.assertEqual(raised, [])

    def test_received_po_lifts_stock_above_reorder_line(self):
        raised = autobuy.scan(self.s)
        self.s.receive_po(raised[0]["id"])
        # now well stocked → no new proposal
        self.assertEqual(autobuy.plan(self.s), [])


if __name__ == "__main__":
    unittest.main()
