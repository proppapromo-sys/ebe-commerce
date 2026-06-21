import os
import tempfile
import unittest

from ebe.store import Store
from ebe import copywriter


class CopywriterTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)
        self.s.upsert_products([
            {"sku": "A", "name": "Alpha", "cost": 2, "sell": 10},
            {"sku": "B", "name": "Beta", "cost": 3, "sell": 15, "description": "<p>already written</p>"},
        ])
        # stub the model call — no network, deterministic
        self._orig = copywriter._generate
        copywriter._generate = lambda product, brand=None: {
            "description": "Buy %s now." % product["name"],
            "bullets": ["Durable", "Great <value>"],
            "seo_title": "%s | Shop" % product["name"],
        }

    def tearDown(self):
        copywriter._generate = self._orig
        self.s.close()
        os.remove(self.path)

    def test_to_html_escapes_and_wraps(self):
        html = copywriter._to_html({"description": "Tom & Jerry", "bullets": ["a < b", "c"]})
        self.assertIn("<p>Tom &amp; Jerry</p>", html)
        self.assertIn("<li>a &lt; b</li>", html)
        self.assertTrue(html.startswith("<p>"))

    def test_describe_product_builds_html(self):
        out = copywriter.describe_product({"sku": "A", "name": "Alpha", "sell": 10})
        self.assertIn("Buy Alpha now.", out["html"])
        self.assertIn("Durable", out["html"])
        self.assertIn("Great &lt;value&gt;", out["html"])      # escaped

    def test_into_store_skips_existing_writes_missing(self):
        res = copywriter.describe_into_store(self.s)
        self.assertEqual(res["written"], ["A"])
        self.assertEqual(res["skipped"], ["B"])
        a = self.s.product("A")
        self.assertIn("Buy Alpha now.", a["description"])
        self.assertEqual(a["name"], "Alpha")                   # name preserved (merge)

    def test_overwrite_redoes_existing(self):
        res = copywriter.describe_into_store(self.s, overwrite=True)
        self.assertEqual(set(res["written"]), {"A", "B"})
        self.assertIn("Buy Beta now.", self.s.product("B")["description"])

    def test_only_filter_and_failure_capture(self):
        def boom(product, brand=None):
            raise RuntimeError("no credit")
        copywriter._generate = boom
        res = copywriter.describe_into_store(self.s, only=["A"])
        self.assertEqual(res["written"], [])
        self.assertEqual(res["failed"][0][0], "A")
        self.assertIn("no credit", res["failed"][0][1])


if __name__ == "__main__":
    unittest.main()
