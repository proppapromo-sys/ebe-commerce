#!/usr/bin/env python3
"""
sourcing.py — BRANCH 1: WHICH PRODUCTS TO SOURCE.

Decides what to buy in — but only after EVERY marketplace fee is subtracted (the trap
most sellers fall into) and only as a SMALL test batch first (scale later, once it
proves it sells). The original EBE "product picker", regrown on the Universal Genome.

  python -m ebe sourcing
"""
from __future__ import annotations

from ..genome import EdgeModel, Risk, Execution, LearningEyes, Machine
from ..fees import FeeModel, AMAZON_FBA, MERCH_APPAREL


def _fees_for(item, default: FeeModel) -> FeeModel:
    """Apparel pays the apparel vig (higher referral + returns); everything else the default."""
    return MERCH_APPAREL if item.get("category") == "apparel" or item.get("is_apparel") else default


# 🧠 BRAIN — edge = ROI after ALL fees. (Most products look fine until you subtract the vig.)
class SourcingEdge(EdgeModel):
    def __init__(self, fee_model: FeeModel = AMAZON_FBA):
        self.fee_model = fee_model

    def fair(self, p):
        return 1.0                                                   # break-even ROI
    def mine(self, p):
        fm = _fees_for(p, self.fee_model)
        return fm.roi(p["sell"], p["cost"]) + 1.0                    # your true return-on-cost
    # edge() = mine − fair = ROI after fees (e.g. 0.6 = +60% ROI on cost)


# ❤️ HEART — risk first. Order a SMALL TEST BATCH; never tie up too much in one unproven SKU.
class SourcingRisk(Risk):
    def __init__(self, capital, max_per=0.20, min_edge=0.30, test_units=15, min_monthly=100):
        super().__init__(capital, min_edge=min_edge, max_per=max_per)
        self.test_units = test_units          # prove it sells before you scale
        self.min_monthly = min_monthly        # no demand → don't even test

    def kelly(self, p, edge):
        return edge

    def stake(self, p, edge):
        if p["monthly_sales"] < self.min_monthly:
            return 0.0
        batch = self.test_units * p["cost"]   # cost of a small test order
        cap = self.max_per * self.bankroll
        return round(min(batch, cap), 2)


# ✋ HANDS — confirm-first "source a test batch"
class SourcingExec(Execution):
    def __init__(self, fee_model: FeeModel = AMAZON_FBA):
        self.fee_model = fee_model

    def place(self, p, stake, live=False):
        fm = _fees_for(p, self.fee_model)
        units = int(stake / p["cost"]) if p["cost"] else 0
        net = fm.net_unit(p["sell"], p["cost"])
        tag = "" if live else "[dry-run] "
        print("    %s📦 SOURCE %-22s %3d units · $%-6.0f  (ROI %3.0f%% after fees · $%.2f net/unit)"
              % (tag, p["name"], units, stake, fm.roi(p["sell"], p["cost"]) * 100, net))


# 👁️ EYES — recognise the kind of product; LEARN which kinds actually sell at profit.
# trust() now comes from LearningEyes (a table earned on the journal); pass trust_table=
# journal.pattern_trust(journal.read()) and proven niches start casting confirm/veto votes.
class SourcingEyes(LearningEyes):
    def detect(self, p):
        pats = [{"name": "niche:" + p.get("category", "?"), "dir": 1}]
        if p.get("competition", 0) >= 0.8:
            pats.append({"name": "saturated", "dir": -1})            # crowded → bearish
        if p.get("monthly_sales", 0) >= 500 and p.get("competition", 1) <= 0.5:
            pats.append({"name": "rising_demand", "dir": 1})
        return pats


def build(feed, capital=2000, fee_model: FeeModel = AMAZON_FBA, trust_table=None, journal=None) -> Machine:
    return Machine(feed, SourcingEdge(fee_model), SourcingRisk(capital),
                   SourcingEyes(trust_table), SourcingExec(fee_model),
                   name="sourcing", journal=journal)
