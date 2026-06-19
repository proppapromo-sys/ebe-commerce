import unittest

from ebe.ai.eyes import AIEyes
from ebe.branches.sourcing import build
from ebe.catalog.feeds import ListFeed
from ebe.catalog.product import Product
from ebe.fees import AMAZON_FBA


def stub(patterns_by_id):
    seen = {"calls": 0}
    def _detect(item, images=None):
        seen["calls"] += 1
        return patterns_by_id.get(item["id"], [])
    _detect.seen = seen
    return _detect


class AIEyesTests(unittest.TestCase):
    def test_detect_returns_named_patterns(self):
        eyes = AIEyes(detect_fn=stub({"P1": [{"name": "trend:rising", "dir": 1}]}))
        self.assertEqual(eyes.detect({"id": "P1"}), [{"name": "trend:rising", "dir": 1}])

    def test_caches_per_item(self):
        fn = stub({"P1": [{"name": "x", "dir": 1}]})
        eyes = AIEyes(detect_fn=fn)
        eyes.detect({"id": "P1"}); eyes.detect({"id": "P1"})
        self.assertEqual(fn.seen["calls"], 1)             # second read hits the cache

    def test_patterns_are_inert_until_the_journal_proves_them(self):
        # AI names a bullish pattern, but with no trust table it does NOT graduate -> no vote
        eyes = AIEyes(detect_fn=stub({"P1": [{"name": "trend:rising", "dir": 1}]}))
        self.assertEqual(eyes.confirm({"id": "P1"}), [])
        # once the record proves it, the same pattern votes
        proven = AIEyes(trust_table={"trend:rising": 0.9},
                        detect_fn=stub({"P1": [{"name": "trend:rising", "dir": 1}]}))
        self.assertIn("trend:rising", proven.confirm({"id": "P1"}))

    def test_proven_bearish_pattern_vetoes_in_the_machine(self):
        # a graduated bearish AI pattern makes sourcing defensively skip the product
        prods = [Product("P1", "thing", "home", cost=5, sell=22, monthly_sales=800, competition=0.4)]
        eyes = AIEyes(trust_table={"saturated-design": 0.9},
                      detect_fn=stub({"P1": [{"name": "saturated-design", "dir": -1}]}))
        m = build(ListFeed(prods), fee_model=AMAZON_FBA, eyes=eyes)
        self.assertEqual(m.cycle(), [])                   # vetoed despite strong ROI


if __name__ == "__main__":
    unittest.main()
