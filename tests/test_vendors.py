import os
import tempfile
import unittest

from ebe.store import Store
from ebe import autobuy


def _store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = Store(path)
    s.upsert_products([
        {"sku": "CHARCOAL", "name": "Coconut charcoal", "category": "hookah",
         "cost": 10.0, "sell": 0, "lead_time_days": 20, "on_hand": 2, "monthly_sales": 120,
         "supplier": "Default Co"},
    ])
    return s, path


class VendorBiddingTests(unittest.TestCase):
    def setUp(self):
        self.s, self.path = _store()

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_best_offer_picks_cheapest_eligible(self):
        self.s.upsert_offers([
            {"sku": "CHARCOAL", "supplier": "Pricey", "unit_cost": 9.5, "min_qty": 1},
            {"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 7.0, "min_qty": 100},
            {"sku": "CHARCOAL", "supplier": "Mid", "unit_cost": 8.0, "min_qty": 1},
        ])
        self.assertEqual(self.s.best_offer("CHARCOAL", qty=500)["supplier"], "Cheap")
        # tiny order can't meet Cheap's MOQ → Mid wins
        self.assertEqual(self.s.best_offer("CHARCOAL", qty=10)["supplier"], "Mid")

    def test_offers_upsert_is_keyed_by_sku_supplier(self):
        self.s.upsert_offers([{"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 7.0}])
        self.s.upsert_offers([{"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 6.5}])  # update
        offers = self.s.offers_for("CHARCOAL")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["unit_cost"], 6.5)

    def test_autobuy_uses_winning_vendor_and_reports_savings(self):
        self.s.upsert_offers([
            {"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 7.0, "min_qty": 50, "pack_size": 24},
        ])
        prop = autobuy.plan(self.s)[0]
        self.assertEqual(prop["supplier"], "Cheap")        # auction winner, not Default Co
        self.assertEqual(prop["unit_cost"], 7.0)
        self.assertEqual(prop["qty"] % 24, 0)              # rounded up to whole packs
        self.assertGreater(prop["savings"], 0)             # cheaper than the $10 default cost

    def test_no_offers_falls_back_to_default_cost(self):
        prop = autobuy.plan(self.s)[0]
        self.assertEqual(prop["supplier"], "Default Co")
        self.assertEqual(prop["unit_cost"], 10.0)
        self.assertEqual(prop["savings"], 0.0)

    def test_raised_po_carries_the_winning_vendor(self):
        self.s.upsert_offers([{"sku": "CHARCOAL", "supplier": "Cheap", "unit_cost": 7.0, "min_qty": 1}])
        autobuy.scan(self.s)
        po = self.s.purchase_orders("draft")[0]
        self.assertEqual(po["supplier"], "Cheap")
        self.assertEqual(po["unit_cost"], 7.0)


if __name__ == "__main__":
    unittest.main()
