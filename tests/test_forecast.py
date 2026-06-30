import unittest

from ebe.forecast import cash_calendar, windows, venue_calendar, runway
from ebe.catalog.product import Product, Variant
from ebe.catalog.feeds import sample_live_catalog
from ebe.venue.sample import sample_menu, sample_consumables, sample_sales


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


class RunwayTests(unittest.TestCase):
    def test_runway_flags_shortfall(self):
        rows = cash_calendar(sample_live_catalog())
        w = windows(rows)
        rw = runway(w, capital=1000)
        self.assertTrue(any(v < 0 for v in rw.values()))      # store needs far more than $1k
        rich = runway(w, capital=10 ** 9)
        self.assertTrue(all(v > 0 for v in rich.values()))


class VenueForecastTests(unittest.TestCase):
    def test_consumables_projected_with_runout(self):
        rows = venue_calendar(sample_sales(), sample_menu(), sample_consumables())
        ids = {r["id"] for r in rows}
        self.assertIn("charcoal_coco", ids)                   # hot consumable on the horizon
        # charcoal is below its reorder point already -> due NOW
        cal = {r["id"]: r for r in rows}
        self.assertEqual(cal["charcoal_coco"]["days_until"], 0.0)

    def test_venue_windows_cumulative(self):
        w = windows(venue_calendar(sample_sales(), sample_menu(), sample_consumables()))
        self.assertLessEqual(w[7], w[90])


if __name__ == "__main__":
    unittest.main()
