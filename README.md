# ebe-commerce
PRODUCT PICKER
#!/usr/bin/env python3
"""
genome.py — THE UNIVERSAL GENOME. The reusable skeleton behind both EBE machines
(the stock trader AND the betting engine). Implement the seven organs for YOUR
domain; the Machine wires them into the same risk-first, forward-validated loop.
Any truth-driven software — trading, betting, ops, bidding, resource allocation —
is the same organism with different cells.

THE FIVE LAWS (the DNA — never break them):
  1. Risk-first, not prediction-first.            (survive before you win)
  2. Edge = your number vs the world's number.    (no edge → no action)
  3. Forward-validate before real stakes.         (the truth-meter)
  4. Recognise + remember, don't predict.         (trust is earned on your record)
  5. Confirm-first, never chase.                  (no revenge, no size-up on a streak)

HOW TO BUILD ANY SOFTWARE FROM THIS:
  1. Implement the ABCs (DataFeed, EdgeModel, Risk, Execution, Eyes, TruthMeter).
  2. Hand them to Machine(...).
  3. Call .run_forever() — one process, own clock, self-healing (see WATCHDOG.md).
Run this file for a tiny end-to-end demo.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod


# ── 👂 EARS — where truth enters ──────────────────────────────────────────────
class DataFeed(ABC):
    @abstractmethod
    def candidates(self) -> list:
        """The things you could act on right now — each a dict your organs read."""


# ── 🧠 BRAIN — your estimate vs the world's; the edge gate ────────────────────
class EdgeModel(ABC):
    @abstractmethod
    def fair(self, item) -> float:   # the world's fair estimate (de-vigged / consensus)
        ...

    @abstractmethod
    def mine(self, item) -> float:   # YOUR estimate
        ...

    def edge(self, item) -> float:
        return self.mine(item) - self.fair(item)


# ── ❤️ HEART — risk. BUILD THIS ORGAN FIRST. ─────────────────────────────────
class Risk(ABC):
    def __init__(self, bankroll, min_edge=0.02, max_per=0.02, daily_stop=0.10):
        self.bankroll = bankroll
        self.min_edge = min_edge          # the edge gate (your "regime ON")
        self.max_per = max_per            # never risk more than this per action
        self.daily_stop = daily_stop      # halt the day past this loss
        self.day_pnl = 0.0
        self.killed = False               # kill-switch

    @abstractmethod
    def kelly(self, item, edge) -> float:
        """Full-Kelly fraction of bankroll for this action (we use a quarter of it)."""

    def stake(self, item, edge) -> float:
        f = max(0.0, min(0.25 * self.kelly(item, edge), self.max_per))   # ¼-Kelly, capped
        return round(f * self.bankroll, 2)

    def gate(self, item, edge):
        """Confirm-first decision — the heart can always VETO. (ok, stake, reason)."""
        if self.killed:
            return (False, 0.0, "kill-switch active")
        if self.day_pnl <= -self.daily_stop * self.bankroll:
            return (False, 0.0, "daily stop hit")
        if edge < self.min_edge:
            return (False, 0.0, "no edge (%.1f%% < %.1f%%)" % (edge * 100, self.min_edge * 100))
        s = self.stake(item, edge)
        return (True, s, "edge %.1f%% · stake %.2f" % (edge * 100, s)) if s > 0 else (False, 0.0, "size 0")


# ── ✋ HANDS — confirm-first execution ────────────────────────────────────────
class Execution(ABC):
    @abstractmethod
    def place(self, item, stake, live=False):
        """Place the action (dry-run unless live). Log it — paper actions ARE the record."""


# ── 👁️ EYES — recognise + remember + learn (Cyclops) ─────────────────────────
class Eyes(ABC):
    @abstractmethod
    def detect(self, item) -> list:
        """Named patterns present on this item: [{'name':..., 'dir': +1/-1/0}, ...]."""

    @abstractmethod
    def trust(self, pattern_name) -> float:
        """Blended backtest-prior + live-forward trust. ~0.5 until it's learned."""

    def graduated(self, pattern_name, min_trust=0.55) -> bool:
        return self.trust(pattern_name) >= min_trust      # earns a vote only when proven

    def confirm(self, item) -> list:
        return [p["name"] for p in self.detect(item) if p.get("dir", 0) > 0 and self.graduated(p["name"])]

    def veto(self, item) -> list:
        return [p["name"] for p in self.detect(item) if p.get("dir", 0) < 0 and self.graduated(p["name"])]


# ── 🩸 TRUTH-METER — the FAST forward-validation signal (CLV / t-stat / …) ────
class TruthMeter(ABC):
    @abstractmethod
    def score(self, placed_action) -> float:
        """Did you beat the world's later/closing estimate? >0 = real edge, proven fast."""


# ── 🔄 THE MACHINE — the universal loop + resilience ─────────────────────────
class Machine:
    """Wires the organs into one risk-first, forward-validated pass — the same loop
    that runs the EBE trader and the betting engine. run_forever() = the seamless,
    self-healing process (pair with a supervisor/watchdog for crash + reboot cover)."""

    def __init__(self, feed: DataFeed, edge: EdgeModel, risk: Risk, eyes: Eyes,
                 exe: Execution, name="machine"):
        self.feed, self.edge, self.risk, self.eyes, self.exe, self.name = feed, edge, risk, eyes, exe, name

    def cycle(self):
        tickets = []
        for item in self.feed.candidates():
            iid = item.get("id", "?")
            e = self.edge.edge(item)
            if self.eyes.veto(item):                                   # 👁️ proven-bad → defensive skip
                print("  veto  %-10s — 👁️ %s" % (iid, self.eyes.veto(item))); continue
            ok, stake, why = self.risk.gate(item, e)                   # ❤️ edge + Kelly + caps + stop
            if not ok:
                print("  pass  %-10s — %s" % (iid, why)); continue
            conf = self.eyes.confirm(item)
            print("  🎯 %-10s %s%s" % (iid, why, (" · ✅ " + ",".join(conf)) if conf else ""))
            tickets.append((item, stake))                             # ✋ hand to execution (confirm-first)
        return tickets

    def run_forever(self, interval_s=300, is_open=lambda: True):
        """One process, own clock, never dies."""
        while True:
            try:
                if is_open():
                    print("── %s cycle ──" % self.name)
                    self.cycle()
                time.sleep(interval_s)
            except KeyboardInterrupt:
                return
            except Exception as ex:
                print("cycle error (continuing):", ex)
                time.sleep(30)


# ── tiny end-to-end demo: a trivial domain implementing every organ ──────────
if __name__ == "__main__":
    class _Feed(DataFeed):
        def candidates(self):
            return [{"id": "A", "world": 0.50, "you": 0.57, "k": 0.10},   # +7% edge
                    {"id": "B", "world": 0.50, "you": 0.51, "k": 0.02},   # +1% edge (below gate)
                    {"id": "C", "world": 0.50, "you": 0.60, "k": 0.20}]   # +10% edge

    class _Edge(EdgeModel):
        def fair(self, it): return it["world"]
        def mine(self, it): return it["you"]

    class _Risk(Risk):
        def kelly(self, it, edge): return it["k"]

    class _Eyes(Eyes):
        def detect(self, it): return []        # no patterns graduated yet → inert
        def trust(self, name): return 0.5

    class _Exe(Execution):
        def place(self, it, stake, live=False): print("    placed", it["id"], stake)

    m = Machine(_Feed(), _Edge(), _Risk(bankroll=1000), _Eyes(), _Exe(), name="demo")
    print("UNIVERSAL GENOME demo — one cycle:")
    m.cycle()
