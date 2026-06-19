import os
import tempfile
import unittest

from ebe.store import Store
from ebe import autobuy, purchasing


class PurchasingTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "M2-Navy", "name": "Cap Navy", "category": "apparel", "cost": 7, "sell": 24,
             "lead_time_days": 25, "on_hand": 5, "monthly_sales": 150, "supplier": "Apparel Mill Co"},
            {"sku": "P3", "name": "Yoga mat", "category": "fitness", "cost": 14, "sell": 45,
             "lead_time_days": 30, "on_hand": 10, "monthly_sales": 300, "supplier": "Generic Imports LLC"},
        ])
        self.s.upsert_suppliers([
            {"name": "Apparel Mill Co", "email": "orders@mill.test", "min_order": 250, "lead_time_days": 21},
        ])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_record_sales_drops_stock(self):
        self.assertEqual(self.s.record_sales({"M2-Navy": 3, "GHOST": 9}), 1)  # only known SKU
        self.assertEqual(self.s.product("M2-Navy")["on_hand"], 2)

    def test_pos_group_by_supplier_with_contact(self):
        autobuy.scan(self.s)                      # raise drafts for the low SKUs
        doc = purchasing.po_document(self.s)
        self.assertIn("Apparel Mill Co", doc)
        self.assertIn("orders@mill.test", doc)    # contact merged from suppliers table
        self.assertIn("Generic Imports LLC", doc)
        self.assertIn("TOTAL TO AUTHORISE", doc)
        self.assertIn("Cap Navy", doc)

    def test_supplier_without_contact_is_flagged(self):
        autobuy.scan(self.s)
        doc = purchasing.po_document(self.s)
        # Generic Imports LLC has no row in suppliers table → prompt to add one
        self.assertIn("No contact on file", doc)

    def test_empty_when_no_orders(self):
        self.assertIn("No open purchase orders", purchasing.po_document(self.s))

    def test_load_supplier_rows_parses_csv(self):
        fd, p = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("name,email,lead_time_days,min_order,notes\n")
                fh.write("Acme,acme@x.test,18,300,fast\n")
            rows = purchasing.load_supplier_rows(p)
            self.assertEqual(rows[0]["name"], "Acme")
            self.assertEqual(rows[0]["lead_time_days"], 18)
            self.assertEqual(rows[0]["min_order"], 300.0)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
