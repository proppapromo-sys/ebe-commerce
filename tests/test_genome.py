import unittest

from ebe.genome import DataFeed, EdgeModel, Risk, BlindEyes, Execution, Machine


class _Feed(DataFeed):
    def candidates(self):
        return [{"id": "win", "edge": 0.10}, {"id": "flat", "edge": 0.0}]


class _Edge(EdgeModel):
    def fair(self, it): return 0.0
    def mine(self, it): return it["edge"]


class _Risk(Risk):
    def kelly(self, it, edge): return edge


class _Exe(Execution):
    def __init__(self): self.placed = []
    def place(self, it, stake, live=False): self.placed.append((it["id"], stake))


class GenomeTests(unittest.TestCase):
    def test_edge_gate_clears_only_real_edge(self):
        m = Machine(_Feed(), _Edge(), _Risk(1000, min_edge=0.02), BlindEyes(), _Exe())
        tickets = m.cycle()
        self.assertEqual([t[0]["id"] for t in tickets], ["win"])

    def test_place_routes_to_hands(self):
        exe = _Exe()
        m = Machine(_Feed(), _Edge(), _Risk(1000), BlindEyes(), exe)
        m.cycle(place=True)
        self.assertEqual([p[0] for p in exe.placed], ["win"])

    def test_kill_switch_vetoes_everything(self):
        r = _Risk(1000)
        r.killed = True
        m = Machine(_Feed(), _Edge(), r, BlindEyes(), _Exe())
        self.assertEqual(m.cycle(), [])

    def test_daily_stop_only_fires_on_real_loss(self):
        # bankroll 0 must NOT trip the stop (0 <= 0 edge case); branches that
        # override stake() then size normally instead of being halted.
        r = _Risk(0)
        _, _, reason = r.gate({"id": "x"}, 0.10)
        self.assertNotEqual(reason, "daily stop hit")


if __name__ == "__main__":
    unittest.main()
