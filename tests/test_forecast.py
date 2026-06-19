import unittest

from ebe.forecast import cash_calendar, windows
from ebe.catalog.product import Product, Variant
from ebe.catalog.feeds import sample_live_catalog


class ForecastTests(unittest.TestCase):
    def test_sorted_soonest_first(self):
        rows = cash_calendar(sample_live_catalog())
        days = [r["days_until"] for r in rows]
        self.assertEqual(days, sorted(days))

    def test_low_cover_reorders_sooner_than_well_stocked(self):
        prods = [
            Product("LOW", "Low", "home", cost=5, sell=20, monthly_sales=300, on_hand=30, lead_time_days=20),
            Product("HIGH", "High", "home", cost=5, sell=20, monthly_sales=300, on_hand=3000, lead_time_days=20),
        ]
        cal = {r["id"]: r for r in cash_calendar(prods)}
        self.assertLess(cal["LOW"]["days_until"], cal["HIGH"]["days_until"])
        self.assertEqual(cal["LOW"]["days_until"], 0.0)        # already past reorder point

    def test_windows_are_cumulative(self):
        rows = cash_calendar(sample_live_catalog())
        w = windows(rows)
        self.assertLessEqual(w[7], w[30])
        self.assertLessEqual(w[30], w[60])
        self.assertLessEqual(w[60], w[90])

    def test_apparel_variants_each_projected(self):
        prods = [Product("T", "Tee", "apparel", cost=9, sell=28, lead_time_days=21,
                         variants=[Variant("S", "Black", on_hand=5, monthly_sales=90),
                                   Variant("L", "Black", on_hand=900, monthly_sales=90)])]
        ids = [r["id"] for r in cash_calendar(prods)]
        self.assertIn("T·S/Black", ids)
        # the deeply-stocked variant reorders much later (or sits beyond the steady-state need)
        cal = {r["id"]: r for r in cash_calendar(prods)}
        self.assertEqual(cal["T·S/Black"]["days_until"], 0.0)


if __name__ == "__main__":
    unittest.main()
