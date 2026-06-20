import os
import tempfile
import unittest

from ebe.store import Store
from ebe import autopilot, sync


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        # one SKU well under its reorder line so a draft gets raised
        self.s.upsert_products([{"sku": "A", "name": "thing", "cost": 5, "sell": 20,
                                 "on_hand": 0, "monthly_sales": 300, "lead_time_days": 14}])
        self._orig_chans = sync.configured_channels
        sync.configured_channels = lambda: []      # no network in tests

    def tearDown(self):
        sync.configured_channels = self._orig_chans
        self.s.close()
        os.remove(self.path)

    def test_cycle_raises_draft_and_logs(self):
        r = autopilot.cycle(self.s)
        self.assertEqual(r["channels"], 0)         # nothing configured
        self.assertGreaterEqual(r["drafts"], 1)    # A is at 0 on hand
        self.assertGreater(r["cash"], 0)
        self.assertEqual(r["errors"], [])
        kinds = [e["kind"] for e in self.s.events()]
        self.assertIn("autopilot", kinds)          # the cycle was recorded

    def test_cycle_no_buy_raises_nothing(self):
        r = autopilot.cycle(self.s, buy=False)
        self.assertEqual(r["drafts"], 0)
        self.assertEqual(self.s.purchase_orders("draft"), [])

    def test_cycle_does_not_double_order(self):
        autopilot.cycle(self.s)                     # raises a draft for A
        before = len(self.s.purchase_orders("draft"))
        autopilot.cycle(self.s)                     # A already has one open → no dup
        after = len(self.s.purchase_orders("draft"))
        self.assertEqual(before, after)

    def test_run_stops_after_cycles_without_sleeping(self):
        seen = []
        slept = []
        autopilot.run(self.s, every_minutes=1, cycles=2,
                      on_cycle=lambda n, r: seen.append(n),
                      sleep_fn=lambda secs: slept.append(secs))
        self.assertEqual(seen, [1, 2])
        self.assertEqual(slept, [60])               # sleeps once between cycles, never after the last

    def test_sync_error_is_captured_not_raised(self):
        sync.configured_channels = lambda: ["amazon"]
        orig = sync.sync_all
        sync.sync_all = lambda *a, **k: {"amazon": {"error": "no creds"}}
        try:
            r = autopilot.cycle(self.s)
            self.assertTrue(any("sync:amazon" in e for e in r["errors"]))
            self.assertGreaterEqual(r["drafts"], 1)   # re-buy still runs despite sync error
        finally:
            sync.sync_all = orig


if __name__ == "__main__":
    unittest.main()
