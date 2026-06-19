import os
import tempfile
import unittest

from ebe.journal import Journal, category_trust
from ebe.edges import score, rank
from ebe.profile import PROFILES
from ebe.fees import AMAZON_FBA
from ebe.adapters.prices import load_alt_sources, DictPriceSource
from ebe.arbitrage import cross_channel


class CategoryTrustTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)

    def tearDown(self):
        os.remove(self.path)

    def test_winning_category_climbs_losing_sinks(self):
        j = Journal(self.path)
        for i in range(8):
            j.record_decision("edges", {"id": "W%d" % i, "category": "hookah"}, 0, 0.7)
            j.record_outcome("edges", "W%d" % i, 1.0)
            j.record_decision("edges", {"id": "L%d" % i, "category": "kitchen"}, 0, 0.7)
            j.record_outcome("edges", "L%d" % i, -1.0)
        ct = category_trust(j.read())
        self.assertGreater(ct["hookah"], 0.6)
        self.assertLess(ct["kitchen"], 0.4)


class LearnedScoreTests(unittest.TestCase):
    def test_learned_sharpens_proven_damps_losers(self):
        it = {"category": "hookah", "sell": 15, "cost": 3, "monthly_sales": 600, "competition": 0.3}
        base = score(it, PROFILES["generic"], AMAZON_FBA).composite
        up = score(it, PROFILES["generic"], AMAZON_FBA, learned={"hookah": 1.0}).composite
        down = score(it, PROFILES["generic"], AMAZON_FBA, learned={"hookah": 0.0}).composite
        self.assertGreater(up, base)
        self.assertLess(down, base)

    def test_neutral_trust_is_no_op(self):
        it = {"category": "home", "sell": 25, "cost": 7, "monthly_sales": 900, "competition": 0.5}
        base = score(it, PROFILES["generic"], AMAZON_FBA).composite
        same = score(it, PROFILES["generic"], AMAZON_FBA, learned={"home": 0.5}).composite
        self.assertAlmostEqual(base, same)


class CrossChannelSourceTests(unittest.TestCase):
    def test_csv_sources_drive_cross_channel(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as fh:
            fh.write("channel,identifier,price\nwalmart,A1,16.40\nebay,A1,15.90\n")
        try:
            alt = load_alt_sources(path)
            self.assertEqual({s.name for s in alt}, {"walmart", "ebay"})
            sources = [DictPriceSource("amazon", {"A1": 22.0})] + alt
            r = cross_channel("A1", sources)
            self.assertEqual(r["buy_channel"], "ebay")     # cheapest
            self.assertEqual(r["sell_channel"], "amazon")  # dearest
            self.assertGreater(r["edge"], 0)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
