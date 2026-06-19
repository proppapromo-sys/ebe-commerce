import types
import unittest

from ebe import dashboard


def _args(**kw):
    base = dict(fees="amazon-fba", products=None, costs=None, profile="hookah", capital=None, port=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


class DashboardRenderTests(unittest.TestCase):
    def test_data_has_all_sections(self):
        d = dashboard._data(_args())
        for key in ("ret", "inv", "pr", "ad", "src", "cal", "win", "ed"):
            self.assertIn(key, d)
        self.assertTrue(d["ed"])                       # edge ranking present

    def test_render_produces_html_with_sections(self):
        page = dashboard.render(dashboard._data(_args()))
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("EBE&nbsp;COMMAND", page)
        self.assertIn("Today", page)
        self.assertIn("Cash forecast", page)
        self.assertIn("True edge", page)
        self.assertIn("CORNER", page)                  # at least one cornerable lane for hookah profile

    def test_capital_runway_shown(self):
        page = dashboard.render(dashboard._data(_args(capital=5000)))
        self.assertTrue("SHORT" in page or "headroom" in page)

    def test_html_escapes_names(self):
        # a malicious-looking product name must be escaped, not injected
        page = dashboard.render(dashboard._data(_args()))
        self.assertNotIn("<script", page.lower())

    def test_landscape_venue_and_switcher_panels(self):
        page = dashboard.render(dashboard._data(_args()))
        self.assertIn("Landscape", page)
        self.assertIn("Venue supplies", page)
        self.assertIn("/?profile=hookah", page)        # clickable profile switcher
        self.assertIn("http-equiv=refresh", page)      # auto-refresh

    def test_query_overrides_profile(self):
        a = dashboard._req_args(_args(profile="generic"), "profile=hookah&capital=2500")
        self.assertEqual(a.profile, "hookah")
        self.assertEqual(a.capital, 2500.0)


if __name__ == "__main__":
    unittest.main()
