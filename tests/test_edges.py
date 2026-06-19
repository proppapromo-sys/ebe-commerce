import unittest

from ebe import edges
from ebe.edges import score, rank, weights_for, recurrence_edge, competition_edge, arbitrage_edge
from ebe.profile import PROFILES, Profile
from ebe.fees import AMAZON_FBA


class SignalTests(unittest.TestCase):
    def test_recurrence_moat_for_consumables(self):
        self.assertEqual(recurrence_edge({"category": "hookah"}), 1.0)
        self.assertEqual(recurrence_edge({"category": "kitchen"}), 0.3)
        self.assertEqual(recurrence_edge({"category": "x", "consumable": True}), 1.0)

    def test_competition_edge_is_open_lane(self):
        self.assertAlmostEqual(competition_edge({"competition": 0.2}), 0.8)
        self.assertAlmostEqual(competition_edge({"competition": 0.9}), 0.1)

    def test_arbitrage_from_price_gap(self):
        self.assertAlmostEqual(arbitrage_edge({"sell": 20, "alt_price": 14}), 1.0)   # 30% gap
        self.assertEqual(arbitrage_edge({"sell": 20}), 0.5)                          # unknown -> neutral


class WeightTests(unittest.TestCase):
    def test_weights_normalise(self):
        self.assertAlmostEqual(sum(weights_for(PROFILES["generic"]).values()), 1.0)

    def test_goals_tilt_weights(self):
        plain = weights_for(Profile("p"))
        margin = weights_for(Profile("p", goals=["high-margin"]))
        self.assertGreater(margin["margin"], plain["margin"])
        recurring = weights_for(Profile("p", goals=["recurring"]))
        self.assertGreater(recurring["recurrence"], plain["recurrence"])


class ScoreTests(unittest.TestCase):
    def test_all_seven_angles_present(self):
        e = score({"category": "hookah", "sell": 15, "cost": 3, "monthly_sales": 600, "competition": 0.3},
                  PROFILES["hookah"], AMAZON_FBA)
        self.assertEqual(set(e.signals), {"margin", "demand", "competition", "advantage",
                                          "recurrence", "timing", "arbitrage"})
        self.assertTrue(0 <= e.composite <= 1 and 0 <= e.moat <= 1)

    def test_defensible_profitable_consumable_is_cornerable(self):
        # open lane + consumable + your advantage + healthy margin -> CORNER
        it = {"category": "hookah", "sell": 15, "cost": 3, "monthly_sales": 700, "competition": 0.25}
        self.assertEqual(score(it, PROFILES["hookah"], AMAZON_FBA).verdict, "CORNER")

    def test_crowded_one_off_is_not_cornerable(self):
        it = {"category": "kitchen", "sell": 24, "cost": 6, "monthly_sales": 1500, "competition": 0.95}
        self.assertNotEqual(score(it, PROFILES["generic"], AMAZON_FBA).verdict, "CORNER")

    def test_rank_orders_by_composite(self):
        rows = [{"category": "kitchen", "sell": 24, "cost": 6, "monthly_sales": 100, "competition": 0.95},
                {"category": "hookah", "sell": 15, "cost": 3, "monthly_sales": 800, "competition": 0.2}]
        ranked = rank(rows, PROFILES["hookah"], AMAZON_FBA)
        self.assertEqual(ranked[0].item["category"], "hookah")
        self.assertGreaterEqual(ranked[0].composite, ranked[1].composite)


if __name__ == "__main__":
    unittest.main()
