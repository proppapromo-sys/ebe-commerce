#!/usr/bin/env python3
"""
returns.py — BRANCH 6: STOP THE RETURN LEAK.

Every other branch chases profit IN; this one plugs profit leaking OUT. A SKU returning
ABOVE its category's normal rate is bleeding margin invisibly — a tee that "runs small"
at 35% returns vs a 20% baseline is eating the profit sourcing/pricing worked to make.

  • edge  = actual return rate − the category baseline baked into the fee model
  • stake = $/month you'd recover by fixing it (excess returns × cost per return)
  • Heart only flags MATERIAL leaks (above a $ threshold), so you fix the few that matter.

  python -m ebe returns --fees amazon-apparel
"""
from __future__ import annotations

from ..genome import DataFeed, EdgeModel, Risk, Execution, LearningEyes, Machine
from ..fees import FeeModel, AMAZON_FBA

# Normal return rate by category — the bar a SKU must exceed to count as leaking.
# Independent of the marketplace fee model (apparel runs hot everywhere).
RETURN_BASELINE = {
    "apparel": 0.20, "shoes": 0.25, "electronics": 0.10, "home": 0.05,
    "kitchen": 0.05, "fitness": 0.06, "beauty": 0.06, "toys": 0.05, "pet": 0.05,
}


def sample_returns() -> list:
    """Per-SKU return data for the last period. Swap for your Seller-Central returns export."""
    return [
        {"id": "M1", "name": "Graphic tee (your brand)", "category": "apparel", "sell": 28, "cost": 9,
         "fulfilment": 5, "units_sold": 300, "units_returned": 105, "top_reason": "size"},   # runs small
        {"id": "M2", "name": "Embroidered cap", "category": "apparel", "sell": 24, "cost": 7,
         "fulfilment": 4, "units_sold": 230, "units_returned": 46, "top_reason": "color"},    # at baseline
        {"id": "P1", "name": "LED strip lights", "category": "home", "sell": 22, "cost": 5,
         "fulfilment": 4, "units_sold": 800, "units_returned": 40, "top_reason": "defective"},  # normal
        {"id": "P3", "name": "Yoga mat (premium)", "category": "fitness", "sell": 45, "cost": 14,
         "fulfilment": 6, "units_sold": 300, "units_returned": 45, "top_reason": "quality"},    # leaking
    ]


class ReturnsFeed(DataFeed):
    def __init__(self, rows):
        self.rows = rows
    def candidates(self):
        return list(self.rows)


def return_rate(r):
    return r["units_returned"] / r["units_sold"] if r.get("units_sold") else 0.0


# 🧠 BRAIN — mine = this SKU's return rate; fair = the category norm (fee model's return_rate).
class ReturnsEdge(EdgeModel):
    def __init__(self, fee_model: FeeModel = AMAZON_FBA):
        self.fee_model = fee_model

    def fair(self, r):
        base = RETURN_BASELINE.get(r.get("category"), self.fee_model.return_rate)
        r["_baseline"] = base
        return base

    def mine(self, r):
        rate = return_rate(r)
        r["_rate"] = rate
        return rate
    # edge = actual − baseline = EXCESS return rate (the recoverable part)


# ❤️ HEART — only act on a material leak; "stake" = the monthly $ you'd stop bleeding.
class ReturnsRisk(Risk):
    def __init__(self, min_excess=0.05, min_bleed=50.0):
        super().__init__(bankroll=0, min_edge=min_excess, max_per=1.0)
        self.min_bleed = min_bleed              # ignore trivial leaks

    def kelly(self, r, edge):
        return edge

    def stake(self, r, edge):
        excess_units = edge * r.get("units_sold", 0)              # returns above baseline / month
        cost_per_return = r.get("fulfilment", 5) + r.get("cost", 0)  # return shipping + the unit
        bleed = excess_units * cost_per_return
        return round(bleed, 2) if bleed >= self.min_bleed else 0.0


# ✋ HANDS — surface the leak + the likely fix.
class ReturnsExec(Execution):
    def place(self, r, stake, live=False):
        tag = "" if live else "[dry-run] "
        reason = r.get("top_reason")
        hint = {"size": "→ fix sizing chart / add fit photos", "quality": "→ supplier QC or cut",
                "defective": "→ supplier QC", "color": "→ fix listing photos/description"}.get(reason, "")
        print("    %s🩹 FIX %-22s %3.0f%% returns (norm %2.0f%%) · $%.0f/mo bleeding  [%s] %s"
              % (tag, r["name"], r.get("_rate", 0) * 100, r.get("_baseline", 0) * 100,
                 stake, reason or "?", hint))


# 👁️ EYES — learn which return REASONS actually predict a dud (recorded, not auto-veto).
class ReturnsEyes(LearningEyes):
    def detect(self, r):
        reason = r.get("top_reason")
        return [{"name": "reason:" + reason, "dir": 0}] if reason else []


def build(rows=None, fee_model: FeeModel = AMAZON_FBA, trust_table=None, journal=None) -> Machine:
    rows = sample_returns() if rows is None else rows
    return Machine(ReturnsFeed(rows), ReturnsEdge(fee_model), ReturnsRisk(),
                   ReturnsEyes(trust_table), ReturnsExec(), name="returns", journal=journal)
