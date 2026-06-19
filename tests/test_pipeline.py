import unittest

from ebe.ai.ears import normalize_listings
from ebe import edges as edgemod
from ebe.profile import PROFILES
from ebe.fees import AMAZON_FBA


class PipelineChainTests(unittest.TestCase):
    """Ears (normalize) -> true-edge scoring is the pipeline; verify the chain end to end offline."""

    def test_listings_flow_into_ranked_edges(self):
        canned = {
            "tips": {"name": "Hookah mouth tips", "category": "hookah", "cost": 0.03,
                     "pack_size": 1000, "sell": 0.15, "moq": 10, "notes": ""},
            "chopper": {"name": "Veg chopper", "category": "kitchen", "cost": 6.0,
                        "pack_size": 1, "sell": 24.0, "moq": 500, "notes": ""},
        }
        prods = normalize_listings(["tips", "chopper"], normalize_fn=lambda r: canned[r])
        items = [p.as_item() for p in prods]
        ranked = edgemod.rank(items, PROFILES["hookah"], AMAZON_FBA)
        self.assertEqual(len(ranked), 2)
        for e in ranked:
            self.assertIn(e.verdict, ("CORNER", "STRONG", "TEST", "pass"))
        # personalization flows through the chain: the hookah operator scores the hookah
        # listing higher than a generic seller would (advantage + recurrence moat)
        hk = next(it for it in items if it["category"] == "hookah")
        self.assertGreater(edgemod.score(hk, PROFILES["hookah"], AMAZON_FBA).composite,
                           edgemod.score(hk, PROFILES["generic"], AMAZON_FBA).composite)


if __name__ == "__main__":
    unittest.main()
