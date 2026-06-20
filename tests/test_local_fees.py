import unittest

from ebe.fees import PRESETS, LOCAL, AMAZON_FBA


class LocalFeeTests(unittest.TestCase):
    def test_local_is_registered(self):
        self.assertIn("local", PRESETS)
        self.assertIs(PRESETS["local"], LOCAL)

    def test_local_beats_marketplace_on_bulky_low_value(self):
        # to-go boxes: $8 cost, $18 local price — loses on FBA, wins local
        cost, sell = 8.0, 18.0
        self.assertGreater(LOCAL.net_unit(sell, cost), AMAZON_FBA.net_unit(sell, cost))
        self.assertGreater(LOCAL.margin(sell, cost), 0.45)        # healthy local margin
        self.assertLess(AMAZON_FBA.net_unit(sell, cost), LOCAL.net_unit(sell, cost) - 4)

    def test_local_has_no_marketplace_or_ad_drag(self):
        self.assertEqual(LOCAL.referral_pct, 0.0)
        self.assertEqual(LOCAL.ad_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
