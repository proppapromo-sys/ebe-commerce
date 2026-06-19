#!/usr/bin/env python3
"""
edges.py — THE TRUE EDGE. Profit is one angle; a defensible position is many stacked.

A single ROI number tells you a thing is profitable today. It does NOT tell you whether you
can OWN it — whether competitors can copy you tomorrow. This module scores every independent
edge angle the data exposes, fuses them (weighted by the operator's goals), and reads how
CORNERABLE each opportunity is: margin you keep, demand that's real, a lane that's open, an
advantage only you have, a product that re-sells itself, momentum, and price gaps to arbitrage.

  margin · demand · competition · advantage · recurrence · timing · arbitrage  ──▶  TRUE EDGE
"""
from __future__ import annotations

from dataclasses import dataclass

from .fees import AMAZON_FBA, MERCH_APPAREL

# Categories whose products get re-bought (a moat: recurring revenue, not one-and-done).
CONSUMABLE = {"hookah", "bar", "takeout", "pet", "beauty", "health", "grocery", "office"}
TREND = {"rising": 0.85, "flat": 0.5, "declining": 0.2}


def _fm(it, default):
    return MERCH_APPAREL if it.get("category") == "apparel" else default


def _clamp(x):
    return max(0.0, min(1.0, x))


# ── the seven edge angles (each 0..1) ────────────────────────────────────────
def margin_edge(it, fm):
    """ROI after every fee, normalised so ~80% ROI = a full-strength margin edge."""
    return _clamp(_fm(it, fm).roi(it.get("sell", 0), it.get("cost", 1)) / 0.8)


def demand_edge(it):
    """Real volume — 1000+ units/mo is a full demand edge."""
    return _clamp(it.get("monthly_sales", 0) / 1000.0)


def competition_edge(it):
    """Open lane. The fewer sellers crowding it, the more of it you can take."""
    return _clamp(1.0 - it.get("competition", 0.5))


def advantage_edge(it, profile):
    """The angle competitors can't copy: YOUR real-world advantage in this category."""
    return _clamp(profile.fit(it) / 0.3) if profile else 0.0


def recurrence_edge(it):
    """A product that re-sells itself (consumable) is a moat; one-and-done is not."""
    if it.get("consumable") or it.get("category") in CONSUMABLE:
        return 1.0
    return 0.3


def timing_edge(it):
    """Momentum — riding a rising trend beats fighting a fading one."""
    return TREND.get(it.get("trend", "flat"), 0.5)


def arbitrage_edge(it):
    """A price gap to another channel you can buy-low/sell-high (neutral if unknown)."""
    alt = it.get("alt_price")
    if alt and it.get("sell"):
        return _clamp(((it["sell"] - alt) / it["sell"]) / 0.30)   # 30% gap = full edge
    return 0.5


SIGNALS = {
    "margin":      lambda it, p, fm: margin_edge(it, fm),
    "demand":      lambda it, p, fm: demand_edge(it),
    "competition": lambda it, p, fm: competition_edge(it),
    "advantage":   lambda it, p, fm: advantage_edge(it, p),
    "recurrence":  lambda it, p, fm: recurrence_edge(it),
    "timing":      lambda it, p, fm: timing_edge(it),
    "arbitrage":   lambda it, p, fm: arbitrage_edge(it),
}

BASE_WEIGHTS = {"margin": 0.24, "demand": 0.18, "competition": 0.18,
                "advantage": 0.15, "recurrence": 0.12, "timing": 0.08, "arbitrage": 0.05}


def weights_for(profile):
    """Goals tilt the weights — a 'recurring' operator values moats; 'high-margin' values margin."""
    w = dict(BASE_WEIGHTS)
    goals = set(getattr(profile, "goals", []) or [])
    if "high-margin" in goals:
        w["margin"] += 0.10
    if "recurring" in goals:
        w["recurrence"] += 0.10
    if "fast-growth" in goals:
        w["demand"] += 0.10
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


@dataclass
class TrueEdge:
    item: dict
    signals: dict          # the seven angle scores
    composite: float       # weighted fusion (0..1)
    moat: float            # how defensible: competition + recurrence + advantage
    verdict: str           # CORNER | STRONG | TEST | pass


def score(it, profile=None, fee_model=AMAZON_FBA) -> TrueEdge:
    sig = {k: _clamp(fn(it, profile, fee_model)) for k, fn in SIGNALS.items()}
    w = weights_for(profile)
    composite = sum(w[k] * sig[k] for k in sig)
    moat = (sig["competition"] + sig["recurrence"] + sig["advantage"]) / 3.0
    if moat >= 0.6 and sig["margin"] >= 0.4:
        verdict = "CORNER"          # defensible AND profitable -> you can own this
    elif composite >= 0.6:
        verdict = "STRONG"
    elif composite >= 0.45:
        verdict = "TEST"
    else:
        verdict = "pass"
    return TrueEdge(it, sig, composite, moat, verdict)


def rank(rows, profile=None, fee_model=AMAZON_FBA):
    """Every opportunity scored across all angles, best true edge first."""
    return sorted((score(it, profile, fee_model) for it in rows),
                  key=lambda e: e.composite, reverse=True)
