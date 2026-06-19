#!/usr/bin/env python3
"""
genome.py — THE UNIVERSAL GENOME for EBE Commerce.

The reusable skeleton behind every "branch" of the seller engine (sourcing,
pricing, restock, ad-spend, ...). Implement the seven organs for YOUR decision;
the Machine wires them into the same risk-first, forward-validated loop.

THE FIVE LAWS (the DNA — never break them):
  1. Risk-first, not prediction-first.            (survive before you win)
  2. Edge = your number vs the world's number.    (no edge -> no action)
  3. Forward-validate before real stakes.         (the truth-meter)
  4. Recognise + remember, don't predict.         (trust is earned on your record)
  5. Confirm-first, never chase.                  (no revenge, no size-up on a streak)

HOW TO GROW A NEW BRANCH FROM THIS:
  1. Implement the ABCs (DataFeed, EdgeModel, Risk, Execution, Eyes[, TruthMeter]).
  2. Hand them to Machine(...).
  3. Call .cycle() once, or .run_forever() for a live process.
Run this file for a tiny end-to-end demo:  python -m ebe.genome
"""
from __future__ import annotations

import math
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


# A shared exposure ledger: one cap on total capital committed across ALL branches/SKUs
# in a run, so clearing many actions can't quietly tie up more than you'll allow.
class Portfolio:
    def __init__(self, cap):
        self.cap = float(cap)
        self.committed = 0.0

    @property
    def free(self):
        return max(0.0, self.cap - self.committed)

    def can_commit(self, stake):
        return stake <= self.free + 1e-9

    def commit(self, stake):
        self.committed += stake
        return self.committed


# ── ❤️ HEART — risk. BUILD THIS ORGAN FIRST. ─────────────────────────────────
class Risk(ABC):
    def __init__(self, bankroll, min_edge=0.02, max_per=0.02, daily_stop=0.10, portfolio=None):
        self.bankroll = bankroll
        self.min_edge = min_edge          # the edge gate (your "regime ON")
        self.max_per = max_per            # never risk more than this per action
        self.daily_stop = daily_stop      # halt the day past this loss
        self.day_pnl = 0.0
        self.killed = False               # kill-switch
        self.portfolio = portfolio        # optional shared exposure cap across branches

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
        if self.day_pnl < 0 and self.day_pnl <= -self.daily_stop * self.bankroll:
            return (False, 0.0, "daily stop hit")
        if edge < self.min_edge:
            return (False, 0.0, "no edge (%.1f%% < %.1f%%)" % (edge * 100, self.min_edge * 100))
        s = self.stake(item, edge)
        if s <= 0:
            return (False, 0.0, "size 0")
        if self.portfolio is not None and not self.portfolio.can_commit(s):   # 💰 global cap
            return (False, 0.0, "portfolio cap (free $%.0f)" % self.portfolio.free)
        if self.portfolio is not None:
            self.portfolio.commit(s)
        return (True, s, "edge %.1f%% · stake %.2f" % (edge * 100, s))


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


# A do-nothing pair of eyes: a branch can start blind and grow sight later.
class BlindEyes(Eyes):
    def detect(self, item):
        return []

    def trust(self, name):
        return 0.5


# 👁️ LEARNING EYES — trust is read from a table earned on the record (law 4 made real).
# detect() stays domain-specific in subclasses; trust() graduates patterns as the
# journal proves them. Build the table with journal.pattern_trust(journal.read()).
class LearningEyes(Eyes):
    def __init__(self, trust_table=None):
        self.trust_table = dict(trust_table or {})

    def trust(self, name):
        return self.trust_table.get(name, 0.5)   # inert at 0.5 until the record moves it

    def detect(self, item):
        return []


# ── 🩸 TRUTH-METER — the FAST forward-validation signal (CLV / sell-through / …) ─
class TruthMeter(ABC):
    @abstractmethod
    def score(self, placed_action) -> float:
        """Did you beat the world's later estimate? >0 = real edge, proven fast."""


# ── 👂 SANITY GATE — garbage never reaches the Brain ─────────────────────────
_NONNEG = ("sell", "cost", "fulfilment", "monthly_sales", "on_hand",
           "competition", "spend", "ad_sales", "lead_time_days")


def sane_item(item) -> str:
    """Return a reason string if the item is impossible to act on, else None.
    Cheap defence against bad feed rows / scraped junk driving a real decision."""
    for k in _NONNEG:
        if k in item:
            v = item[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return "%s not numeric" % k
            if not math.isfinite(v) or v < 0:
                return "%s invalid (%r)" % (k, v)
    if "cost" in item and item["cost"] <= 0:
        return "cost must be > 0"
    return None


# ── 🔄 THE MACHINE — the universal loop + resilience ─────────────────────────
class Machine:
    """Wires the organs into one risk-first, forward-validated pass — the same loop
    every branch of the seller engine runs. run_forever() = the seamless, self-healing
    process (pair with a supervisor/watchdog for crash + reboot cover)."""

    def __init__(self, feed: DataFeed, edge: EdgeModel, risk: Risk, eyes: Eyes,
                 exe: Execution, name="machine", journal=None, guard=None):
        self.feed, self.edge, self.risk, self.eyes, self.exe, self.name = feed, edge, risk, eyes, exe, name
        self.journal = journal          # optional decision/outcome record (closes the learning loop)
        self.guard = guard or sane_item  # 👂 sanity gate — bad rows never reach the Brain

    def cycle(self, place=False, live=False):
        """One pass. Returns the cleared tickets [(item, stake), ...].
        If place=True, hand each cleared ticket to the hands (dry-run unless live)."""
        tickets = []
        for item in self.feed.candidates():
            iid = item.get("id", "?")
            bad = self.guard(item)                                     # 👂 reject impossible inputs
            if bad:
                print("  drop  %-12s — ⚠️ %s" % (iid, bad)); continue
            e = self.edge.edge(item)
            if self.eyes.veto(item):                                   # 👁️ proven-bad → defensive skip
                print("  veto  %-12s — 👁️ %s" % (iid, self.eyes.veto(item))); continue
            ok, stake, why = self.risk.gate(item, e)                   # ❤️ edge + Kelly + caps + stop
            if not ok:
                print("  pass  %-12s — %s" % (iid, why)); continue
            conf = self.eyes.confirm(item)
            print("  🎯 %-12s %s%s" % (iid, why, (" · ✅ " + ",".join(conf)) if conf else ""))
            tickets.append((item, stake))                             # ✋ hand to execution (confirm-first)
            if self.journal:                                          # 📓 write the record (law 4)
                pats = [p["name"] for p in self.eyes.detect(item)]
                self.journal.record_decision(self.name, item, stake, e, pats)
        if place:
            for item, stake in tickets:
                self.exe.place(item, stake, live=live)
        return tickets

    def run_forever(self, interval_s=300, is_open=lambda: True, place=True, live=False):
        """One process, own clock, never dies."""
        while True:
            try:
                if is_open():
                    print("── %s cycle ──" % self.name)
                    self.cycle(place=place, live=live)
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

    class _Exe(Execution):
        def place(self, it, stake, live=False): print("    placed", it["id"], stake)

    m = Machine(_Feed(), _Edge(), _Risk(bankroll=1000), BlindEyes(), _Exe(), name="demo")
    print("UNIVERSAL GENOME demo — one cycle:")
    m.cycle(place=True)
