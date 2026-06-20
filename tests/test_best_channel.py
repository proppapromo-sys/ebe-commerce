import unittest

from ebe.channels import compare, best_channel
from ebe.profile import PROFILES


def _tips():
    # cheap item: loses on ship channels (flat fee), wins local
    return {"name": "Hookah tips 100pk", "id": "t", "category": "hookah",
            "cost": 1.30, "sell": 5.49, "monthly_sales": 200, "competition": 0.45}


def _charcoal():
    return {"name": "Coco charcoal", "id": "c", "category": "hookah",
            "cost": 3.0, "sell": 14.99, "monthly_sales": 1000, "competition": 0.5}


class BestChannelTests(unittest.TestCase):
    def test_compare_covers_every_preset(self):
        from ebe.fees import PRESETS
        rows = compare(_tips(), PROFILES["hookah"])
        self.assertEqual({r["channel"] for r in rows}, set(PRESETS))

    def test_cheap_item_best_channel_is_local(self):
        best = best_channel(_tips(), PROFILES["hookah"])
        self.assertEqual(best["channel"], "local")          # ship channels lose on a $5.49 item

    def test_dense_item_ships_profitably(self):
        rows = {r["channel"]: r for r in compare(_charcoal(), PROFILES["hookah"])}
        self.assertGreater(rows["amazon-fba"]["net_unit"], 0)

    def test_best_channel_none_when_all_lose(self):
        loser = {"name": "x", "id": "x", "category": "supply", "cost": 20, "sell": 21,
                 "monthly_sales": 10, "competition": 0.9}
        self.assertIsNone(best_channel(loser, PROFILES["generic"]))


if __name__ == "__main__":
    unittest.main()
