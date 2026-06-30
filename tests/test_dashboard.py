import types
import unittest

from ebe import dashboard


def _args(**kw):
    base = dict(fees="amazon-fba", products=None, costs=None, profile="hookah",
                capital=None, port=None, journal=None)
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
        self.assertIn("EBE&nbsp;OS", page)             # default brand (EBE_BRAND overrides)
        self.assertIn("EBE&nbsp;ORB", page)            # the orb identity is constant
        self.assertIn("Today", page)
        self.assertIn("Cash forecast", page)
        self.assertIn("True edge", page)
        self.assertIn("CORNER", page)                  # at least one cornerable lane for hookah profile

    def test_capital_runway_shown(self):
        page = dashboard.render(dashboard._data(_args(capital=5000)))
        self.assertTrue("SHORT" in page or "headroom" in page)

    def test_html_escapes_names(self):
        # The trusted HUD has its own <script>, but DATA must never inject markup.
        page = dashboard.render(dashboard._data(_args()))
        self.assertNotIn("<script>alert", page.lower())   # no injected script
        self.assertNotIn("onerror=", page.lower())        # no injected handler
        self.assertEqual(dashboard._esc("<script>x</script>"),
                         "&lt;script&gt;x&lt;/script&gt;")  # escaper neutralizes markup

    def test_brief_tab_renders(self):
        page = dashboard.render_brief(_args())
        self.assertIn("Morning brief", page)
        self.assertIn("One move", page)
        self.assertIn("data-count", page)              # animated metric tiles

    def test_sheet_view_groups_or_empties(self):
        page = dashboard.render_sheet(_args())
        self.assertIn("Order sheets", page)            # renders even with no live POs

    def test_reprice_tab_shows_floor_and_strategy(self):
        page = dashboard.render_reprice(_args(strategy="undercut"))
        self.assertIn("Pricing", page)
        self.assertIn("floor", page.lower())           # floor analysis present without keys
        self.assertIn("data-count", page)              # animated metric tiles

    def test_rebuy_tab_renders_proposals(self):
        import os
        import tempfile
        from ebe.store import Store
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            s = Store(path)                                # real catalog: one SKU under the line
            s.upsert_products([{"sku": "A", "name": "Widget", "cost": 2, "sell": 10,
                                "on_hand": 0, "monthly_sales": 300, "lead_time_days": 14}])
            s.close()
            page = dashboard.render_rebuy(_args(db=path))
            self.assertIn("Restock", page)
            self.assertIn("Proposed re-buys", page)        # A is under the reorder line
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_landscape_nav_and_switcher_panels(self):
        page = dashboard.render(dashboard._data(_args()))
        self.assertIn("Landscape", page)
        self.assertIn("/catalog?profile=", page)       # generalized nav tab
        self.assertIn("/live?profile=", page)          # market tab
        self.assertIn("http-equiv=refresh", page)      # auto-refresh

    def test_subpages_render_forms_without_keys(self):
        self.assertIn("action='/live'", dashboard.render_live(_args(), ""))
        self.assertIn("textarea", dashboard.render_supply(_args(), ""))
        venue = dashboard.render_venue(_args(), "")
        self.assertIn("POS counts", venue)
        self.assertIn("Coconut charcoal", venue)       # venue computes with no key needed

    def test_query_overrides_profile(self):
        a = dashboard._req_args(_args(profile="generic"), "profile=hookah&capital=2500")
        self.assertEqual(a.profile, "hookah")
        self.assertEqual(a.capital, 2500.0)

    def test_learning_panel_and_buttons_with_journal(self):
        import os
        import tempfile
        from ebe.journal import Journal
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            j = Journal(path)
            for i in range(8):                          # hookah proven winner
                j.record_outcome("edges", "hk%d" % i, 1.0, category="hookah")
            page = dashboard.render(dashboard._data(_args(journal=path)))
            self.assertIn("Learning", page)
            self.assertIn("/record?id=", page)          # clickable win/loss buttons
            self.assertIn("hookah", page)               # proven category in the trust table
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
