import os
import tempfile
import unittest

from ebe.adapters.stripe import sum_amounts, charges_total
from ebe.store import Store
from ebe import brief


class StripeMappingTests(unittest.TestCase):
    def test_balance_cents_to_units(self):
        self.assertEqual(sum_amounts([{"amount": 12345}, {"amount": 5500}]), 178.45)
        self.assertEqual(sum_amounts(None), 0.0)

    def test_charges_total_counts_only_succeeded(self):
        charges = [
            {"amount": 2800, "status": "succeeded"},
            {"amount": 2400, "status": "succeeded", "refunded": True},   # refunded → excluded
            {"amount": 9900, "status": "failed"},                        # failed → excluded
            {"amount": 1500, "status": "succeeded"},
        ]
        out = charges_total(charges)
        self.assertEqual(out, {"revenue": 43.0, "charges": 2})


class BriefCashTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "A", "name": "thing", "cost": 5, "sell": 20,
                                 "on_hand": 100, "monthly_sales": 30}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_compose_has_cash_key_none_without_stripe(self):
        # no STRIPE_SECRET_KEY in the test env → cash gracefully None, brief still composes
        os.environ.pop("STRIPE_SECRET_KEY", None)
        from ebe.adapters import config
        config._LOADED = True
        b = brief.compose(self.s)
        self.assertIn("cash", b)
        self.assertIsNone(b["cash"])

    def test_render_text_shows_cash_when_present(self):
        b = brief.compose(self.s)
        b["cash"] = {"available": 4200.0, "pending": 0.0, "revenue30": 9800.0, "charges30": 53}
        txt = brief.render_text(b)
        self.assertIn("CASH (Stripe)", txt)
        self.assertIn("4200", txt)


if __name__ == "__main__":
    unittest.main()
