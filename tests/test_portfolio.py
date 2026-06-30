import unittest

from ebe.genome import Portfolio, Machine, DataFeed, EdgeModel, Risk, BlindEyes, Execution


class PortfolioTests(unittest.TestCase):
    def test_ledger_math(self):
        p = Portfolio(100)
        self.assertTrue(p.can_commit(60))
        p.commit(60)
        self.assertEqual(p.free, 40)
        self.assertFalse(p.can_commit(60))     # only 40 left
        self.assertTrue(p.can_commit(40))


class _Feed(DataFeed):
    def candidates(self):
        return [{"id": "A", "cost": 5, "sell": 22, "k": 1.0},
                {"id": "B", "cost": 5, "sell": 22, "k": 1.0},
                {"id": "C", "cost": 5, "sell": 22, "k": 1.0}]


class _Edge(EdgeModel):
    def fair(self, it): return 0.0
    def mine(self, it): return 0.5


class _Risk(Risk):
    def kelly(self, it, edge): return 1.0
    def stake(self, it, edge): return 75.0      # each action wants $75


class _Exe(Execution):
    def place(self, it, s, live=False): pass


class PortfolioGateTests(unittest.TestCase):
    def test_cap_stops_overcommitment_across_items(self):
        # cap $100: the first $75 clears, the rest can't fit
        risk = _Risk(1000, min_edge=0.0, portfolio=Portfolio(100))
        ids = [t[0]["id"] for t in Machine(_Feed(), _Edge(), risk, BlindEyes(), _Exe()).cycle()]
        self.assertEqual(ids, ["A"])

    def test_without_cap_all_clear(self):
        risk = _Risk(1000, min_edge=0.0)         # no portfolio -> unchanged behaviour
        ids = [t[0]["id"] for t in Machine(_Feed(), _Edge(), risk, BlindEyes(), _Exe()).cycle()]
        self.assertEqual(ids, ["A", "B", "C"])

    def test_cap_shared_across_two_machines(self):
        shared = Portfolio(160)                   # enough for exactly two $75 actions
        for _ in range(2):
            risk = _Risk(1000, min_edge=0.0, portfolio=shared)
            Machine(_Feed(), _Edge(), risk, BlindEyes(), _Exe()).cycle()
        self.assertEqual(shared.committed, 150)   # 2 cleared total, 3rd+ blocked
        self.assertFalse(shared.can_commit(75))


if __name__ == "__main__":
    unittest.main()
