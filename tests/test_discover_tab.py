import os
import types
import unittest

from ebe import dashboard as d
from ebe.adapters import config


def _args():
    return types.SimpleNamespace(profile="generic", fees="amazon-fba", capital=None, db=":memory:")


class FakeProd:
    def __init__(self, item):
        self._item = item
    def as_item(self):
        return self._item


class DiscoverTabTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("KEEPA_API_KEY", None)
        config._LOADED = True

    def test_form_shows_and_prompts_without_search(self):
        config._LOADED = True
        os.environ["KEEPA_API_KEY"] = "k"
        html = d.render_discover(_args(), {})
        self.assertIn("Discover products to sell", html)
        self.assertIn("/discover", html)               # the search form
        self.assertIn("Search</button>", html)
        self.assertIn("Pick a category", html)         # prompt before searching

    def test_warns_without_keepa(self):
        config._LOADED = True
        os.environ.pop("KEEPA_API_KEY", None)
        html = d.render_discover(_args(), {})
        self.assertIn("Connect market data", html)

    def test_search_ranks_results_with_add_links(self):
        config._LOADED = True
        os.environ["KEEPA_API_KEY"] = "k"
        import ebe.adapters.keepa as keepa
        orig = keepa.discover_candidates
        keepa.discover_candidates = lambda **kw: [
            FakeProd({"id": "B0AAA", "name": "Widget", "category": "home",
                      "cost": 4, "sell": 24, "monthly_sales": 900, "competition": 0.4})]
        try:
            html = d.render_discover(_args(), {"category": ["home"], "min_sales": ["500"]})
            self.assertIn("results", html)
            self.assertIn("Widget", html)
            self.assertIn("/catalog-add?", html)       # one-click add to catalog
            self.assertIn("B0AAA", html)
        finally:
            keepa.discover_candidates = orig

    def test_discover_in_nav(self):
        self.assertTrue(any(k == "discover" for _, _, k in d.NAV))


if __name__ == "__main__":
    unittest.main()
