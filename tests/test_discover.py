import unittest

from ebe.adapters.keepa import build_selection, discover_candidates


class FakeKeepa:
    """Stand-in Keepa client: records the selection, returns canned products."""
    def __init__(self, asins, products):
        self._asins, self._products = asins, products
        self.selection = None

    def product_finder(self, selection):
        self.selection = selection
        return self._asins

    def fetch(self, asins):
        return [p for p in self._products if p["asin"] in asins]


def kp(asin, title, price_cents, monthly, offers=5, cat="Home & Kitchen"):
    return {"asin": asin, "title": title, "monthlySold": monthly,
            "categoryTree": [{"name": cat}],
            "stats": {"buyBoxPrice": price_cents, "offerCountFBA": offers}}


class SelectionTests(unittest.TestCase):
    def test_build_selection_maps_filters(self):
        sel = build_selection(category="home", min_monthly=300, min_price=15, max_price=50, max_sellers=8, limit=25)
        self.assertEqual(sel["monthlySold_gte"], 300)
        self.assertEqual(sel["current_BUY_BOX_SHIPPING_gte"], 1500)
        self.assertEqual(sel["current_BUY_BOX_SHIPPING_lte"], 5000)
        self.assertEqual(sel["current_COUNT_NEW_lte"], 8)
        self.assertEqual(sel["perPage"], 25)
        self.assertEqual(sel["rootCategory"], [1055398])

    def test_unknown_category_omits_root(self):
        sel = build_selection(category="nonsense")
        self.assertNotIn("rootCategory", sel)


class DiscoverTests(unittest.TestCase):
    def test_assumes_cost_from_price_ratio(self):
        fake = FakeKeepa(
            asins=["A1", "A2"],
            products=[kp("A1", "Widget", 2000, 500), kp("A2", "Gadget", 4000, 350)])
        prods = discover_candidates(category="home", cost_ratio=0.40, client=fake)
        by_id = {p.id: p for p in prods}
        self.assertEqual(by_id["A1"].sell, 20.0)
        self.assertEqual(by_id["A1"].cost, 8.0)        # 40% of $20
        self.assertEqual(by_id["A2"].cost, 16.0)       # 40% of $40
        self.assertEqual(by_id["A1"].monthly_sales, 500)

    def test_skips_products_with_no_price(self):
        fake = FakeKeepa(asins=["A1"], products=[kp("A1", "NoPrice", -1, 500)])
        self.assertEqual(discover_candidates(client=fake), [])


if __name__ == "__main__":
    unittest.main()
