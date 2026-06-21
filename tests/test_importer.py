import os
import tempfile
import unittest

from ebe.store import Store
from ebe import importer


class SplitTests(unittest.TestCase):
    def test_blank_line_blocks(self):
        text = "Hookah tips 1000pcs $30\n\nCoconut charcoal 1.2kg $2/kg"
        self.assertEqual(len(importer.split_listings(text)), 2)

    def test_one_per_line_when_no_blank_lines(self):
        text = "tips $5\nclamshell $6\ncharcoal $2"
        self.assertEqual(len(importer.split_listings(text)), 3)

    def test_empty(self):
        self.assertEqual(importer.split_listings("   "), [])


class SlugTests(unittest.TestCase):
    def test_slug_basic(self):
        self.assertEqual(importer.slug_sku("Disposable Hookah Tips!!", set()),
                         "DISPOSABLE-HOOKAH-TIPS")

    def test_slug_dedup(self):
        used = {"COCONUT-CHARCOAL"}
        self.assertEqual(importer.slug_sku("Coconut Charcoal", used), "COCONUT-CHARCOAL-2")

    def test_slug_fallback(self):
        self.assertEqual(importer.slug_sku("!!!", set()), "ITEM")


class ImportTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.s = Store(self.path)

    def tearDown(self):
        self.s.close()
        os.remove(self.path)

    def _fake(self, mapping):
        return lambda raw: mapping[raw]

    def test_creates_products_with_generated_skus(self):
        listings = ["Hookah tips 1000pcs $30", "Coconut charcoal 1.2kg $2.50"]
        fake = self._fake({
            listings[0]: {"name": "Hookah Tips 100ct", "category": "hookah", "cost": 1.3, "sell": 5.49},
            listings[1]: {"name": "Coconut Charcoal 1.2kg", "category": "hookah", "cost": 2.5, "sell": 14.99},
        })
        res = importer.import_listings(self.s, listings, normalize_fn=fake)
        self.assertEqual(len(res["created"]), 2)
        skus = [p["sku"] for p in self.s.products()]
        self.assertIn("HOOKAH-TIPS-100CT", skus)
        p = self.s.product("COCONUT-CHARCOAL-1-2KG")
        self.assertEqual(p["cost"], 2.5)
        self.assertEqual(p["sell"], 14.99)
        self.assertEqual(p["category"], "hookah")

    def test_failure_is_captured(self):
        def boom(raw):
            raise RuntimeError("no credit")
        res = importer.import_listings(self.s, ["x"], normalize_fn=boom)
        self.assertEqual(res["created"], [])
        self.assertEqual(len(res["failed"]), 1)
        self.assertIn("no credit", res["failed"][0][1])

    def test_dedup_against_existing_catalog(self):
        self.s.upsert_products([{"sku": "HOOKAH-TIPS", "name": "old"}])
        fake = self._fake({"l": {"name": "Hookah Tips", "cost": 1, "sell": 5}})
        res = importer.import_listings(self.s, ["l"], normalize_fn=fake)
        self.assertEqual(res["created"][0][0], "HOOKAH-TIPS-2")   # didn't collide


if __name__ == "__main__":
    unittest.main()
