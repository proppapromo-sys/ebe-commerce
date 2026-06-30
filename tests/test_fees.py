import unittest

from ebe.fees import FeeModel, AMAZON_FBA, MERCH_APPAREL


class FeeTests(unittest.TestCase):
    def test_net_unit_subtracts_every_fee(self):
        fm = FeeModel("t", referral_pct=0.10, ad_pct=0.10, return_rate=0.05, fulfilment=2.0)
        # fees on $20 = 20*0.25 + 2 = 7 ; net = 20 - 6 - 7 = 7
        self.assertAlmostEqual(fm.net_unit(20, 6), 7.0)

    def test_roi_and_margin(self):
        self.assertAlmostEqual(AMAZON_FBA.roi(30, 8), AMAZON_FBA.net_unit(30, 8) / 8)
        self.assertAlmostEqual(AMAZON_FBA.margin(30, 8), AMAZON_FBA.net_unit(30, 8) / 30)

    def test_apparel_is_harsher_than_standard(self):
        self.assertLess(MERCH_APPAREL.net_unit(30, 8), AMAZON_FBA.net_unit(30, 8))

    def test_breakeven_roas_positive(self):
        self.assertGreater(AMAZON_FBA.breakeven_roas(30, 8), 1.0)


if __name__ == "__main__":
    unittest.main()
