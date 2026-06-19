#!/usr/bin/env python3
"""
journal.py — THE RECORD. Law 4 says trust is earned on your record; this is the record.

Every decision the Machine clears, and every outcome you later observe, is appended as one
JSON line. Feed it back through pattern_trust() to learn which patterns actually pay — that
table drives LearningEyes, so patterns GRADUATE on evidence instead of sitting inert at 0.5.

  decision  →  (later, real sell-through)  →  outcome  →  pattern_trust()  →  LearningEyes
"""
from __future__ import annotations

import json
import os
import time


class Journal:
    """Append-only JSONL record of decisions and outcomes."""

    def __init__(self, path="ebe_journal.jsonl"):
        self.path = path

    def append(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("ts", round(time.time(), 3))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return record

    def record_decision(self, branch, item, stake, edge, patterns=None) -> dict:
        return self.append({
            "kind": "decision", "branch": branch, "id": item.get("id"),
            "name": item.get("name"), "category": item.get("category"),
            "stake": stake, "edge": edge, "patterns": list(patterns or []),
        })

    def record_outcome(self, branch, item_id, score, patterns=None, category=None) -> dict:
        """score > 0 means the action proved out (sold through / beat the world)."""
        return self.append({
            "kind": "outcome", "branch": branch, "id": item_id, "score": score,
            "category": category, "patterns": list(patterns or []),
        })

    def read(self) -> list:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass        # skip a corrupt line rather than die mid-read
        return out


def pattern_trust(records, prior=0.5, prior_weight=10.0) -> dict:
    """Win-rate per pattern, shrunk toward a 0.5 prior so a single lucky hit can't graduate
    (it takes ~3 clean wins to clear the 0.55 vote threshold).
    A 'win' is an outcome score > 0. Patterns are joined from the matching decision when the
    outcome doesn't carry them. Returns {pattern: trust in 0..1} — feed straight to LearningEyes."""
    patterns_by_id = {}
    for r in records:
        if r.get("kind") == "decision":
            patterns_by_id[r.get("id")] = r.get("patterns") or []

    wins, total = {}, {}
    for r in records:
        if r.get("kind") != "outcome":
            continue
        pats = r.get("patterns") or patterns_by_id.get(r.get("id"), [])
        win = 1.0 if (r.get("score") or 0) > 0 else 0.0
        for pat in pats:
            wins[pat] = wins.get(pat, 0.0) + win
            total[pat] = total.get(pat, 0) + 1

    return {pat: (wins[pat] + prior * prior_weight) / (n + prior_weight)
            for pat, n in total.items()}


def category_trust(records, prior=0.5, prior_weight=6.0) -> dict:
    """Win-rate per CATEGORY from scored outcomes (the compounding edge): categories that
    keep paying off climb above 0.5, ones that keep losing sink below. Feed to edges.score(
    learned=...) so proven lanes sharpen and duds get damped every cycle."""
    cat_by_id = {r.get("id"): r.get("category") for r in records if r.get("kind") == "decision"}
    wins, total = {}, {}
    for r in records:
        if r.get("kind") != "outcome":
            continue
        cat = r.get("category") or cat_by_id.get(r.get("id"))
        if not cat:
            continue
        win = 1.0 if (r.get("score") or 0) > 0 else 0.0
        wins[cat] = wins.get(cat, 0.0) + win
        total[cat] = total.get(cat, 0) + 1
    return {cat: (wins[cat] + prior * prior_weight) / (n + prior_weight)
            for cat, n in total.items()}
