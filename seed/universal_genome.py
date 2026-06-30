#!/usr/bin/env python3
"""
universal_genome.py — THE UNIVERSAL GENOME (v2). A complete, self-contained, copy-me seed.

Drop this ONE file into a new project and grow a risk-first, self-learning decision engine
for ANY domain — trading, betting, e-commerce, ops, bidding, resource allocation. Implement
the organs for your domain, hand them to Machine, call .cycle(). Pure standard library.

THE FIVE LAWS (the DNA — never break them):
  1. Risk-first, not prediction-first.            (survive before you win)
  2. Edge = your number vs the world's number.    (no edge -> no action)
  3. Forward-validate before real stakes.         (the truth-meter / journal)
  4. Recognise + remember, don't predict.         (trust is earned on your record)
  5. Confirm-first, never chase.                  (no revenge, no size-up on a streak)

WHAT'S IN THE BOX (v2):
  • Seven organs: DataFeed, EdgeModel, Risk, Execution, Eyes, TruthMeter, + the Machine loop
  • Portfolio        — one exposure cap across everything (the Heart can't over-commit)
  • LearningEyes     — patterns graduate on the record, not on a hunch (laws 3 & 4)
  • sane_item        — a sanity gate so garbage never reaches the Brain
  • Journal          — append-only (or in-memory) record of decisions + outcomes
  • pattern_trust / category_trust — turn the record into learned trust that sharpens you

START A NEW PROJECT:
  1. Subclass DataFeed, EdgeModel, Risk, Execution, Eyes (LearningEyes for learning).
  2. m = Machine(feed, edge, risk, eyes, exe, journal=Journal())
  3. m.cycle(place=True)   # then record outcomes and re-run; it compounds.
Run this file for a full end-to-end demo:  python universal_genome.py
"""
from __future__ import annotations

import json
import math
import os
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


# ── 💰 PORTFOLIO — one exposure cap across ALL actions/branches ───────────────
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
        self.portfolio = portfolio        # optional shared exposure cap

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
        if self.portfolio is not None and not self.portfolio.can_commit(s):
            return (False, 0.0, "portfolio cap (free %.2f)" % self.portfolio.free)
        if self.portfolio is not None:
            self.portfolio.commit(s)
        return (True, s, "edge %.1f%% · stake %.2f" % (edge * 100, s))


# ── ✋ HANDS — confirm-first execution ────────────────────────────────────────
class Execution(ABC):
    @abstractmethod
    def place(self, item, stake, live=False):
        """Place the action (dry-run unless live). Log it — paper actions ARE the record."""


# ── 👁️ EYES — recognise + remember + learn ───────────────────────────────────
class Eyes(ABC):
    @abstractmethod
    def detect(self, item) -> list:
        """Named patterns present on this item: [{'name':..., 'dir': +1/-1/0}, ...]."""

    @abstractmethod
    def trust(self, pattern_name) -> float:
        """Blended prior + live-forward trust. ~0.5 until it's learned."""

    def graduated(self, pattern_name, min_trust=0.55) -> bool:
        return self.trust(pattern_name) >= min_trust      # earns a vote only when proven

    def confirm(self, item) -> list:
        return [p["name"] for p in self.detect(item) if p.get("dir", 0) > 0 and self.graduated(p["name"])]

    def veto(self, item) -> list:
        return [p["name"] for p in self.detect(item) if p.get("dir", 0) < 0 and self.graduated(p["name"])]


class BlindEyes(Eyes):
    """Start blind; grow sight later."""
    def detect(self, item):
        return []

    def trust(self, name):
        return 0.5


class LearningEyes(Eyes):
    """trust() reads a table earned on the journal (laws 3 & 4). Subclass detect() for your
    domain; build the table with pattern_trust(journal.read())."""
    def __init__(self, trust_table=None):
        self.trust_table = dict(trust_table or {})

    def trust(self, name):
        return self.trust_table.get(name, 0.5)

    def detect(self, item):
        return []


# ── 🩸 TRUTH-METER — the FAST forward-validation signal ──────────────────────
class TruthMeter(ABC):
    @abstractmethod
    def score(self, placed_action) -> float:
        """Did you beat the world's later estimate? >0 = real edge, proven fast."""


# ── 👂 SANITY GATE — garbage never reaches the Brain ─────────────────────────
_NONNEG = ("price", "cost", "sell", "stake", "size", "quantity")


def sane_item(item, nonneg=_NONNEG) -> str:
    """Reason string if the item is impossible to act on, else None. Tune `nonneg` per domain."""
    for k in nonneg:
        if k in item:
            v = item[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return "%s not numeric" % k
            if not math.isfinite(v) or v < 0:
                return "%s invalid (%r)" % (k, v)
    if "cost" in item and item["cost"] <= 0:
        return "cost must be > 0"
    return None


# ── 📓 JOURNAL — the record (law 4). File-backed, or in-memory if path is None ──
class Journal:
    def __init__(self, path=None):
        self.path = path
        self._mem = [] if path is None else None

    def append(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("ts", round(time.time(), 3))
        if self.path is None:
            self._mem.append(record)
        else:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        return record

    def record_decision(self, branch, item, stake, edge, patterns=None) -> dict:
        return self.append({"kind": "decision", "branch": branch, "id": item.get("id"),
                            "name": item.get("name"), "category": item.get("category"),
                            "stake": stake, "edge": edge, "patterns": list(patterns or [])})

    def record_outcome(self, branch, item_id, score, patterns=None) -> dict:
        return self.append({"kind": "outcome", "branch": branch, "id": item_id,
                            "score": score, "patterns": list(patterns or [])})

    def read(self) -> list:
        if self.path is None:
            return list(self._mem)
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        return out


def _trust_by(records, field, prior=0.5, prior_weight=10.0):
    """Generic shrunk win-rate keyed by a decision field (pattern or category)."""
    by_id = {r.get("id"): r.get(field) for r in records if r.get("kind") == "decision"}
    wins, total = {}, {}
    for r in records:
        if r.get("kind") != "outcome":
            continue
        win = 1.0 if (r.get("score") or 0) > 0 else 0.0
        keys = r.get(field)
        if field == "patterns":
            keys = r.get("patterns") or by_id.get(r.get("id")) or []
        else:
            keys = [r.get(field) or by_id.get(r.get("id"))]
        for k in keys:
            if not k:
                continue
            wins[k] = wins.get(k, 0.0) + win
            total[k] = total.get(k, 0) + 1
    return {k: (wins[k] + prior * prior_weight) / (n + prior_weight) for k, n in total.items()}


def pattern_trust(records, prior=0.5, prior_weight=10.0) -> dict:
    """Win-rate per PATTERN, shrunk toward 0.5 so a single lucky hit can't graduate."""
    return _trust_by(records, "patterns", prior, prior_weight)


def category_trust(records, prior=0.5, prior_weight=6.0) -> dict:
    """Win-rate per CATEGORY — the compounding edge: proven lanes climb, duds sink."""
    return _trust_by(records, "category", prior, prior_weight)


# ── 🔄 THE MACHINE — the universal loop ──────────────────────────────────────
class Machine:
    def __init__(self, feed: DataFeed, edge: EdgeModel, risk: Risk, eyes: Eyes,
                 exe: Execution, name="machine", journal=None, guard=None):
        self.feed, self.edge, self.risk, self.eyes, self.exe, self.name = feed, edge, risk, eyes, exe, name
        self.journal = journal
        self.guard = guard or sane_item

    def cycle(self, place=False, live=False):
        tickets = []
        for item in self.feed.candidates():
            iid = item.get("id", "?")
            bad = self.guard(item)
            if bad:
                print("  drop  %-12s — ⚠️ %s" % (iid, bad)); continue
            e = self.edge.edge(item)
            if self.eyes.veto(item):
                print("  veto  %-12s — 👁️ %s" % (iid, self.eyes.veto(item))); continue
            ok, stake, why = self.risk.gate(item, e)
            if not ok:
                print("  pass  %-12s — %s" % (iid, why)); continue
            conf = self.eyes.confirm(item)
            print("  🎯 %-12s %s%s" % (iid, why, (" · ✅ " + ",".join(conf)) if conf else ""))
            tickets.append((item, stake))
            if self.journal:
                self.journal.record_decision(self.name, item, stake, e,
                                             [p["name"] for p in self.eyes.detect(item)])
        if place:
            for item, stake in tickets:
                self.exe.place(item, stake, live=live)
        return tickets

    def run_forever(self, interval_s=300, is_open=lambda: True, place=True, live=False):
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


# ── END-TO-END DEMO: a trivial domain implementing every organ + the learning loop ──
if __name__ == "__main__":
    class _Feed(DataFeed):
        def candidates(self):
            return [{"id": "A", "category": "x", "world": 0.50, "you": 0.62, "k": 0.12},  # +12% edge
                    {"id": "B", "category": "y", "world": 0.50, "you": 0.51, "k": 0.02},  # below gate
                    {"id": "C", "category": "x", "world": 0.50, "you": 0.60, "k": 0.20}]  # +10% edge

    class _Edge(EdgeModel):
        def fair(self, it): return it["world"]
        def mine(self, it): return it["you"]

    class _Risk(Risk):
        def kelly(self, it, edge): return it["k"]

    class _Eyes(LearningEyes):
        def detect(self, it): return [{"name": "cat:" + it["category"], "dir": 1}]

    class _Exe(Execution):
        def place(self, it, stake, live=False): print("    placed", it["id"], stake)

    print("UNIVERSAL GENOME v2 — end-to-end demo\n")
    jrnl = Journal()                       # in-memory record
    m = Machine(_Feed(), _Edge(), _Risk(bankroll=1000, min_edge=0.05),
                _Eyes(), _Exe(), journal=jrnl)

    print("cycle 1 (eyes inert at 0.5 — no votes yet):")
    m.cycle(place=True)

    # forward-validate: category 'x' kept paying off
    for r in [d for d in jrnl.read() if d["kind"] == "decision"]:
        jrnl.record_outcome("machine", r["id"], score=1.0 if r["category"] == "x" else -1.0)

    learned = category_trust(jrnl.read())
    print("\nlearned category trust from the record:", {k: round(v, 2) for k, v in learned.items()})
    print("law 4 in action — proven category 'x' now earns trust above the 0.55 vote bar.")
