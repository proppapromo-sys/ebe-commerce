import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(__file__), "..", "seed", "universal_genome.py")
_spec = importlib.util.spec_from_file_location("universal_genome_seed", _PATH)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


class SeedSelfContainedTests(unittest.TestCase):
    """The seed must work entirely on its own — no imports from the ebe package."""

    def test_machine_cycle_and_journal(self):
        class Feed(g.DataFeed):
            def candidates(self):
                return [{"id": "A", "category": "x", "world": 0.5, "you": 0.62, "k": 0.12},
                        {"id": "B", "category": "y", "world": 0.5, "you": 0.51, "k": 0.02}]

        class Edge(g.EdgeModel):
            def fair(self, it): return it["world"]
            def mine(self, it): return it["you"]

        class R(g.Risk):
            def kelly(self, it, edge): return it["k"]

        class Eyes(g.LearningEyes):
            def detect(self, it): return [{"name": "cat:" + it["category"], "dir": 1}]

        class Exe(g.Execution):
            def place(self, it, stake, live=False): pass

        j = g.Journal()                       # in-memory
        m = g.Machine(Feed(), Edge(), R(1000, min_edge=0.05), Eyes(), Exe(), journal=j)
        tickets = m.cycle(place=True)
        self.assertEqual([t[0]["id"] for t in tickets], ["A"])   # B below the gate
        self.assertTrue(any(r["kind"] == "decision" for r in j.read()))

    def test_in_memory_journal_and_category_trust(self):
        j = g.Journal()
        for i in range(8):
            j.record_decision("m", {"id": "W%d" % i, "category": "x"}, 0, 0.6)
            j.record_outcome("m", "W%d" % i, 1.0)
        self.assertGreater(g.category_trust(j.read())["x"], 0.55)

    def test_portfolio_cap_and_sanity_gate(self):
        p = g.Portfolio(50)
        self.assertTrue(p.can_commit(50))
        p.commit(50)
        self.assertFalse(p.can_commit(1))
        self.assertIsNotNone(g.sane_item({"cost": 0}))
        self.assertIsNone(g.sane_item({"cost": 5, "price": 22}))


if __name__ == "__main__":
    unittest.main()
