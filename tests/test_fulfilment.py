import unittest

from ebe.fees import SHOPIFY
from ebe.sourcing_rank import rank_candidates


class FulfilmentTests(unittest.TestCase):
    def test_with_fulfilment_replaces_only_fulfilment(self):
        f = SHOPIFY.with_fulfilment(1.25)
        self.assertEqual(f.fulfilment, 1.25)
        self.assertEqual(f.referral_pct, SHOPIFY.referral_pct)   # everything else unchanged
        self.assertEqual(SHOPIFY.fulfilment, 4.5)                # original untouched (frozen)

    def test_product_fulfilment_lowers_net(self):
        # same product, with and without a per-unit 3PL fee
        base = {"name": "Box", "cost": 25.5, "sell": 47.99, "monthly_sales": 250}
        withff = dict(base, fulfilment=3.0)
        r0 = rank_candidates([base], fee=SHOPIFY)[0]
        r1 = rank_candidates([withff], fee=SHOPIFY)[0]
        # default SHOPIFY fulfilment is 4.5; overriding to 3.0 should IMPROVE net by 1.5
        self.assertAlmostEqual(r1["net_unit"] - r0["net_unit"], 1.5, places=2)

    def test_zero_fulfilment_uses_channel_default(self):
        base = {"name": "Box", "cost": 25.5, "sell": 47.99, "monthly_sales": 250}
        r0 = rank_candidates([base], fee=SHOPIFY)[0]
        r_explicit = rank_candidates([dict(base, fulfilment=0)], fee=SHOPIFY)[0]
        self.assertEqual(r0["net_unit"], r_explicit["net_unit"])  # 0/falsey → channel default


if __name__ == "__main__":
    unittest.main()
