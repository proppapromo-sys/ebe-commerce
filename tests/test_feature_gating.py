import types
import unittest

from ebe import plans, dashboard


class TabAllowedTests(unittest.TestCase):
    def test_core_tabs_open_on_starter(self):
        for k in ("today", "catalog", "rebuy", "reprice", "pnl", "membership", "settings"):
            self.assertTrue(plans.tab_allowed("starter", k))

    def test_advanced_tabs_gated(self):
        self.assertFalse(plans.tab_allowed("starter", "discover"))
        self.assertFalse(plans.tab_allowed("starter", "report"))
        self.assertTrue(plans.tab_allowed("growth", "discover"))
        self.assertTrue(plans.tab_allowed("pro", "report"))


class NavLockTests(unittest.TestCase):
    def _shell_for(self, plan):
        a = types.SimpleNamespace(profile="generic", fees="amazon-fba", capital=None, plan=plan)
        ctx = dashboard._ctx_from_args(a)
        return dashboard._shell(ctx, "today", "<p>x</p>")

    def test_starter_locks_advanced_tabs(self):
        html = self._shell_for("starter")
        self.assertIn("class='locked'", html)
        self.assertIn("🔒", html)

    def test_agency_locks_nothing(self):
        html = self._shell_for("agency")
        self.assertNotIn("class='locked'", html)
        self.assertNotIn("🔒", html)

    def test_no_plan_no_gating(self):
        # standalone (single-user) has no plan → every tab open
        a = types.SimpleNamespace(profile="generic", fees="amazon-fba", capital=None)
        html = dashboard._shell(dashboard._ctx_from_args(a), "today", "<p>x</p>")
        self.assertNotIn("class='locked'", html)
        self.assertNotIn("🔒", html)


if __name__ == "__main__":
    unittest.main()
