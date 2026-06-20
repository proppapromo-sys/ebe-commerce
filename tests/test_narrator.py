import os
import tempfile
import unittest

from ebe.store import Store
from ebe import brief
from ebe.ai import narrator


class NarratorTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([{"sku": "CAP", "name": "Cap", "cost": 7, "sell": 24,
                                 "lead_time_days": 25, "on_hand": 4, "monthly_sales": 150}])

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_facts_only_uses_measured_numbers(self):
        b = brief.compose(self.s, profile="hookah")
        sheet = narrator.facts(b)
        self.assertIn("Stock:", sheet)
        self.assertIn("Re-buy:", sheet)
        self.assertIn("one move that matters", sheet)

    def test_narrate_passes_facts_and_returns_structure(self):
        seen = {}

        def stub_assess(fact_sheet):
            seen["facts"] = fact_sheet
            return {"headline": "Restock the cap today.",
                    "narrative": "You're nearly out of caps and they move fast.",
                    "priorities": ["Approve the cap re-buy", "Send the order"]}

        b = brief.compose(self.s, profile="hookah")
        out = narrator.narrate(b, assess_fn=stub_assess)
        self.assertEqual(out["greeting"], "Good morning.")        # default filled in
        self.assertEqual(out["headline"], "Restock the cap today.")
        self.assertIn("Stock:", seen["facts"])                   # model got the fact sheet
        self.assertEqual(len(out["priorities"]), 2)

    def test_dashboard_ai_button_when_not_requested(self):
        from ebe import dashboard
        import types
        a = types.SimpleNamespace(fees="amazon-fba", products=None, costs=None,
                                  profile="hookah", capital=None, port=None, journal=None)
        page = dashboard.render_brief(a)
        self.assertIn("Ask EBE", page)                           # opt-in button, no paid call


if __name__ == "__main__":
    unittest.main()
