import unittest

from ebe.catalog.feeds import ListFeed, sample_sourcing_catalog, sample_live_catalog
from ebe.catalog.product import Product, Variant
from ebe.branches import sourcing, pricing, inventory, adspend
from ebe.fees import AMAZON_FBA


class SourcingTests(unittest.TestCase):
    def test_only_profitable_high_demand_products_clear(self):
        m = sourcing.build(ListFeed(sample_sourcing_catalog()), fee_model=AMAZON_FBA)
        ids = [t[0]["id"] for t in m.cycle()]
        self.assertIn("P1", ids)        # cheap, high margin, strong demand
        self.assertNotIn("P2", ids)     # thin margin after fees
        self.assertNotIn("P4", ids)     # demand too low to test


class PricingTests(unittest.TestCase):
    def test_proposes_a_price_and_uplift(self):
        m = pricing.build(ListFeed(sample_live_catalog()), fee_model=AMAZON_FBA)
        tickets = m.cycle()
        self.assertTrue(tickets)
        item, stake = tickets[0]
        self.assertIn("_best_price", item)
        self.assertGreaterEqual(stake, 0.0)


class InventoryTests(unittest.TestCase):
    def test_flags_low_cover_skips_well_stocked(self):
        prods = [
            Product("LOW", "Low stock", "home", cost=5, sell=20, monthly_sales=300,
                    on_hand=5, lead_time_days=20),
            Product("HIGH", "Well stocked", "home", cost=5, sell=20, monthly_sales=30,
                    on_hand=2000, lead_time_days=20),
        ]
        m = inventory.build(prods)
        ids = [t[0]["id"] for t in m.cycle()]
        self.assertIn("LOW", ids)
        self.assertNotIn("HIGH", ids)

    def test_apparel_expands_per_variant(self):
        prods = [Product("T", "Tee", "apparel", cost=9, sell=28, lead_time_days=21,
                         variants=[Variant("S", "Black", on_hand=2, monthly_sales=60),
                                   Variant("L", "Black", on_hand=999, monthly_sales=10)])]
        m = inventory.build(prods)
        ids = [t[0]["id"] for t in m.cycle()]
        self.assertIn("T·S/Black", ids)
        self.assertNotIn("T·L/Black", ids)


class AdspendTests(unittest.TestCase):
    def test_scales_winners_passes_losers(self):
        m = adspend.build(fee_model=AMAZON_FBA)
        ids = [t[0]["id"] for t in m.cycle()]
        self.assertIn("C-P1", ids)      # ACOS well under target
        self.assertNotIn("C-M1", ids)   # bleeding above breakeven


if __name__ == "__main__":
    unittest.main()
