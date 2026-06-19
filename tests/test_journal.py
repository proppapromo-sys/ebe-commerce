import os
import tempfile
import unittest

from ebe.journal import Journal, pattern_trust
from ebe.genome import sane_item, Machine, DataFeed, EdgeModel, Risk, LearningEyes, Execution
from ebe.branches.sourcing import SourcingEyes


class JournalTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)

    def tearDown(self):
        os.remove(self.path)

    def test_records_round_trip(self):
        j = Journal(self.path)
        j.record_decision("sourcing", {"id": "P1", "name": "x"}, 75.0, 0.6, ["niche:home"])
        j.record_outcome("sourcing", "P1", score=1.0)
        recs = j.read()
        self.assertEqual(recs[0]["kind"], "decision")
        self.assertEqual(recs[1]["kind"], "outcome")
        self.assertIn("ts", recs[0])

    def test_pattern_graduates_only_after_wins(self):
        j = Journal(self.path)
        # one win shouldn't graduate (prior shrink), several should
        j.record_decision("s", {"id": "A"}, 1, 0.5, ["niche:home"])
        j.record_outcome("s", "A", 1.0)
        trust1 = pattern_trust(j.read())
        self.assertLess(trust1["niche:home"], 0.55)        # not proven yet

        for i in range(8):
            j.record_decision("s", {"id": "W%d" % i}, 1, 0.5, ["niche:home"])
            j.record_outcome("s", "W%d" % i, 1.0)
        trust2 = pattern_trust(j.read())
        self.assertGreater(trust2["niche:home"], 0.55)      # record earned it

    def test_losses_keep_a_pattern_inert(self):
        j = Journal(self.path)
        for i in range(8):
            j.record_decision("s", {"id": "L%d" % i}, 1, 0.5, ["saturated"])
            j.record_outcome("s", "L%d" % i, -1.0)
        self.assertLess(pattern_trust(j.read())["saturated"], 0.5)


class LearningEyesTests(unittest.TestCase):
    def test_eyes_vote_once_the_table_proves_the_pattern(self):
        item = {"id": "P", "category": "home", "competition": 0.4, "monthly_sales": 600}
        blind = SourcingEyes()                                # no table -> inert
        self.assertEqual(blind.confirm(item), [])
        learned = SourcingEyes({"niche:home": 0.9, "rising_demand": 0.9})
        self.assertIn("niche:home", learned.confirm(item))   # now it votes

    def test_machine_writes_to_the_journal(self):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            class F(DataFeed):
                def candidates(self): return [{"id": "X", "cost": 5, "sell": 22, "k": 0.1}]
            class E(EdgeModel):
                def fair(self, it): return 0.0
                def mine(self, it): return 0.1
            class R(Risk):
                def kelly(self, it, e): return it["k"]
            class X(Execution):
                def place(self, it, s, live=False): pass
            j = Journal(path)
            Machine(F(), E(), R(1000), LearningEyes(), X(), name="t", journal=j).cycle()
            recs = j.read()
            self.assertTrue(recs and recs[0]["id"] == "X" and recs[0]["kind"] == "decision")
        finally:
            os.remove(path)


class SanityGateTests(unittest.TestCase):
    def test_rejects_impossible_rows(self):
        self.assertIsNone(sane_item({"cost": 5, "sell": 22}))
        self.assertIsNotNone(sane_item({"cost": 0, "sell": 22}))
        self.assertIsNotNone(sane_item({"cost": -1, "sell": 22}))
        self.assertIsNotNone(sane_item({"cost": 5, "monthly_sales": -3}))
        self.assertIsNotNone(sane_item({"cost": float("nan"), "sell": 1}))

    def test_machine_drops_bad_rows(self):
        class F(DataFeed):
            def candidates(self): return [{"id": "BAD", "cost": 0, "sell": 10},
                                          {"id": "OK", "cost": 5, "sell": 22}]
        class E(EdgeModel):
            def fair(self, it): return 0.0
            def mine(self, it): return 0.5
        class R(Risk):
            def kelly(self, it, e): return 0.2
        class X(Execution):
            def place(self, it, s, live=False): pass
        from ebe.genome import BlindEyes
        ids = [t[0]["id"] for t in Machine(F(), E(), R(1000), BlindEyes(), X()).cycle()]
        self.assertEqual(ids, ["OK"])           # the cost=0 row never reached the gate


if __name__ == "__main__":
    unittest.main()
