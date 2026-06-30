#!/usr/bin/env python3
"""
adspend.py — BRANCH 4: PUT AD MONEY WHERE IT COMPOUNDS.

Every advertised SKU has a breakeven ROAS (return on ad spend) set by its margin after
fees. Beat it with room to spare → pour fuel on. Burn below it → cut before it bleeds.
This branch reads your campaigns' real spend + sales and proposes scale / hold / cut.

Edge = how much headroom you have under your target ACOS.

  python -m ebe adspend
"""
from __future__ import annotations

from ..genome import DataFeed, EdgeModel, Risk, Execution, BlindEyes, Machine
from ..fees import FeeModel, AMAZON_FBA, MERCH_APPAREL


def _fees_for(item, default: FeeModel) -> FeeModel:
    return MERCH_APPAREL if item.get("category") == "apparel" else default


def sample_campaigns() -> list:
    """Each: a SKU's last-30-day ad performance. Swap for your real ad-console export."""
    return [
        {"id": "C-P1", "name": "LED strips",  "category": "home",    "sell": 22, "cost": 5,
         "spend": 600,  "ad_sales": 4200, "target_acos": 0.25},
        {"id": "C-M1", "name": "Graphic tee", "category": "apparel", "sell": 28, "cost": 9,
         "spend": 900,  "ad_sales": 2400, "target_acos": 0.30},
        {"id": "C-M2", "name": "Cap",         "category": "apparel", "sell": 24, "cost": 7,
         "spend": 300,  "ad_sales": 2700, "target_acos": 0.30},
        {"id": "C-P3", "name": "Yoga mat",    "category": "fitness", "sell": 45, "cost": 14,
         "spend": 500,  "ad_sales": 1800, "target_acos": 0.25},
    ]


class CampaignFeed(DataFeed):
    def __init__(self, campaigns):
        self.campaigns = campaigns
    def candidates(self):
        return list(self.campaigns)


def acos(c):
    return c["spend"] / c["ad_sales"] if c["ad_sales"] else float("inf")


# 🧠 BRAIN — edge = headroom under target ACOS (and above breakeven). Positive → scalable.
class AdEdge(EdgeModel):
    def __init__(self, fee_model: FeeModel = AMAZON_FBA):
        self.fee_model = fee_model

    def fair(self, c):
        return 0.0
    def mine(self, c):
        fm = _fees_for(c, self.fee_model)
        be = 1.0 / fm.breakeven_roas(c["sell"], c["cost"])   # breakeven ACOS
        target = min(c.get("target_acos", be), be)
        a = acos(c)
        c["_acos"], c["_breakeven_acos"], c["_target_acos"] = a, be, target
        if target <= 0:
            return 0.0
        return (target - a) / target                          # >0 room to scale, <0 must cut


# ❤️ HEART — scale winners; "stake" = suggested monthly budget change.
class AdRisk(Risk):
    def __init__(self, min_headroom=0.05, scale_step=0.30):
        super().__init__(bankroll=0, min_edge=min_headroom, max_per=1.0)
        self.scale_step = scale_step

    def kelly(self, c, edge):
        return edge
    def stake(self, c, edge):
        return round(c["spend"] * self.scale_step, 2)        # budget to add to a winner


# ✋ HANDS — scale / cut. The brain only graduates scalable campaigns to here;
# losers are surfaced separately so they're never silently ignored.
class AdExec(Execution):
    def place(self, c, stake, live=False):
        tag = "" if live else "[dry-run] "
        print("    %s📈 SCALE  %-16s ACOS %.0f%% (target %.0f%%) · +$%.0f/mo budget"
              % (tag, c["name"], c["_acos"] * 100, c["_target_acos"] * 100, stake))


class AdMachine(Machine):
    """Adds an explicit CUT pass for campaigns bleeding above breakeven."""
    def cycle(self, place=False, live=False):
        tickets = super().cycle(place=place, live=live)
        for c in self.feed.candidates():
            self.edge.edge(c)        # populates _acos / _breakeven_acos
            if c["_acos"] > c["_breakeven_acos"]:
                print("  ✂️  %-12s — CUT: ACOS %.0f%% > breakeven %.0f%% (losing money)"
                      % (c["id"], c["_acos"] * 100, c["_breakeven_acos"] * 100))
        return tickets


def build(campaigns=None, fee_model: FeeModel = AMAZON_FBA) -> Machine:
    campaigns = sample_campaigns() if campaigns is None else campaigns
    return AdMachine(CampaignFeed(campaigns), AdEdge(fee_model), AdRisk(),
                     BlindEyes(), AdExec(), name="adspend")
