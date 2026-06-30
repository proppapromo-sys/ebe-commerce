import unittest

from ebe.ai.ears import to_product, normalize_listings


class EarsTests(unittest.TestCase):
    def test_to_product_maps_normalized_fields(self):
        d = {"name": "Hookah mouth tips", "category": "hookah", "cost": 0.03,
             "pack_size": 1000, "sell": 0.0, "moq": 10, "notes": "OEM"}
        p = to_product(d, 1)
        self.assertEqual(p.id, "S1")
        self.assertEqual(p.category, "hookah")
        self.assertAlmostEqual(p.cost, 0.03)

    def test_normalize_listings_uses_injected_fn(self):
        canned = {
            "tips box": {"name": "Hookah tips", "category": "hookah", "cost": 0.03,
                         "pack_size": 1000, "sell": 0.0, "moq": 10, "notes": ""},
            "charcoal": {"name": "Coco charcoal", "category": "hookah", "cost": 0.06,
                         "pack_size": 72, "sell": 0.0, "moq": 200, "notes": ""},
        }
        def fake(raw):
            return canned[raw]
        prods = normalize_listings(["tips box", "charcoal"], normalize_fn=fake)
        self.assertEqual([p.id for p in prods], ["S1", "S2"])
        self.assertEqual(prods[0].name, "Hookah tips")
        self.assertEqual(prods[1].category, "hookah")

    def test_missing_fields_default_safely(self):
        p = to_product({}, 3)
        self.assertEqual(p.id, "S3")
        self.assertEqual(p.cost, 0.0)
        self.assertEqual(p.category, "other")


if __name__ == "__main__":
    unittest.main()
