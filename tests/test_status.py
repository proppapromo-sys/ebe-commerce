import os
import time
import tempfile
import unittest

from ebe.store import Store
from ebe import status, sync
from ebe.adapters import config


class StatusTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        # make sure no real channel keys leak in from the environment
        config._LOADED = True
        for k in ("SHOPIFY_STORE", "SHOPIFY_TOKEN", "SHOPIFY_CLIENT_ID",
                  "SHOPIFY_CLIENT_SECRET", "SPAPI_REFRESH_TOKEN",
                  "SPAPI_CLIENT_ID", "SPAPI_CLIENT_SECRET"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def test_empty_shop_flags_catalog(self):
        st = status.compose(self.s)
        self.assertEqual(st["products"], 0)
        self.assertEqual(st["health"], "never_run")
        self.assertIn("catalog", st["flag"].lower())

    def test_no_channels_flagged(self):
        self.s.upsert_products([{"sku": "A", "name": "x", "cost": 5, "sell": 20,
                                 "on_hand": 100, "monthly_sales": 10}])
        st = status.compose(self.s)
        self.assertEqual(st["connected"], [])
        self.assertIn("channel", st["flag"].lower())

    def test_fresh_after_autopilot_run(self):
        self.s.upsert_products([{"sku": "A", "name": "x", "cost": 5, "sell": 20,
                                 "on_hand": 100, "monthly_sales": 10}])
        os.environ["SHOPIFY_STORE"] = "g0-ew"
        os.environ["SHOPIFY_CLIENT_ID"] = "cid"
        os.environ["SHOPIFY_CLIENT_SECRET"] = "secret"
        try:
            self.s._log("autopilot", note="sync 1/1ch · drafts 0 ($0)")
            self.s._cx.commit()
            st = status.compose(self.s)
            self.assertEqual(st["health"], "fresh")
            self.assertIn("shopify", st["connected"])
        finally:
            for k in ("SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"):
                os.environ.pop(k, None)

    def test_stale_when_old_run(self):
        self.s.upsert_products([{"sku": "A", "name": "x", "cost": 5, "sell": 20,
                                 "on_hand": 100, "monthly_sales": 10}])
        old = time.time() - (status.STALE_AFTER_HOURS + 1) * 3600
        self.s._cx.execute("INSERT INTO events (ts,kind,note) VALUES (?,?,?)",
                           (old, "autopilot", "old run"))
        self.s._cx.commit()
        st = status.compose(self.s)
        self.assertEqual(st["health"], "stale")
        self.assertIn("h ago", st["last_run_ago"])

    def test_render_is_a_string_with_header(self):
        out = status.render_text(status.compose(self.s))
        self.assertIn("EBE COMMAND · STATUS", out)
        self.assertIsInstance(out, str)

    def test_last_event_helper(self):
        self.assertIsNone(self.s.last_event("autopilot"))
        self.s._log("autopilot", note="first")
        self.s._log("autopilot", note="second")
        self.s._cx.commit()
        self.assertEqual(self.s.last_event("autopilot")["note"], "second")


if __name__ == "__main__":
    unittest.main()
