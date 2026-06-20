import os
import tempfile
import unittest

from ebe.sourcing_rank import rank_candidates, fund_within_budget, summarize, load_candidates
from ebe.fees import SHOPIFY
from ebe.profile import PROFILES


def _cands():
    return [
        {"name": "Coconut charcoal", "id": "c", "category": "hookah", "cost": 3.2, "sell": 14.99,
         "monthly_sales": 420, "competition": 0.35},
        {"name": "Cocktail shaker", "id": "s", "category": "home", "cost": 6.5, "sell": 21.99,
         "monthly_sales": 160, "competition": 0.75},
        {"name": "Loss leader", "id": "l", "category": "home", "cost": 20.0, "sell": 21.0,
         "monthly_sales": 50, "competition": 0.9},     # margin after fees is negative
    ]


class SourcingRankTests(unittest.TestCase):
    def test_rank_orders_by_projected_profit(self):
        ranked = rank_candidates(_cands(), PROFILES["hookah"], SHOPIFY)
        self.assertEqual(ranked[0]["name"], "Coconut charcoal")    # highest $/mo
        self.assertIn(ranked[0]["verdict"], ("CORNER", "STRONG", "TEST"))

    def test_each_row_has_margin_and_edge(self):
        r = rank_candidates(_cands(), PROFILES["generic"], SHOPIFY)[0]
        for key in ("net_unit", "roi", "margin", "composite", "verdict", "monthly_profit"):
            self.assertIn(key, r)

    def test_fund_within_budget_skips_losers_and_respects_cap(self):
        ranked = rank_candidates(_cands(), PROFILES["hookah"], SHOPIFY)
        plan = fund_within_budget(ranked, budget=200, test_units=50)
        names = [c["name"] for c in plan["chosen"]]
        self.assertNotIn("Loss leader", names)                     # negative margin excluded
        self.assertLessEqual(plan["spent"], 200)

    def test_summarize_counts_winners(self):
        summ = summarize(rank_candidates(_cands(), PROFILES["hookah"], SHOPIFY))
        self.assertEqual(summ["count"], 3)
        self.assertGreaterEqual(summ["winners"], 1)

    def test_load_candidates_reads_csv(self):
        fd, p = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("name,category,cost,sell,monthly_sales,competition\n")
                fh.write("Charcoal,hookah,3.2,14.99,420,0.35\n")
            items = load_candidates(p)
            self.assertEqual(items[0]["category"], "hookah")
            self.assertEqual(items[0]["sell"], 14.99)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
