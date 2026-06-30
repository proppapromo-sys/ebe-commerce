#!/usr/bin/env python3
"""
scout.py — READ THE LANDSCAPE, PERSONALLY.

Survey a market through YOUR profile: which opportunities to capitalise on, how crowded
each lane is (open vs leaders-dominate), and where your real-world advantage tilts the odds.
Two operators pointed at identical data get different shortlists — because their edge differs.

  • edge   = ROI-after-fees  +  your profile's advantage in that category
  • Eyes   = read the competitive regime (open lane / leaders dominate)
  • output = a ranked "where to infiltrate" list + a per-category landscape map

  python -m ebe scout --profile hookah
"""
from __future__ import annotations

from ..genome import EdgeModel, Risk, Execution, LearningEyes, Machine, DataFeed
from ..fees import FeeModel, AMAZON_FBA, MERCH_APPAREL


def _fees_for(item, default: FeeModel) -> FeeModel:
    return MERCH_APPAREL if item.get("category") == "apparel" else default


def sample_market() -> list:
    """A spread of candidate products across categories so the landscape is visible.
    Swap for `discover` output (Keepa) to scout a live market."""
    return [
        {"id": "cl_sponge", "name": "Microfiber cleaning cloths",   "category": "home",    "sell": 15, "cost": 3,  "monthly_sales": 600,  "competition": 0.30},
        {"id": "st_bags",   "name": "Reusable storage bags",        "category": "kitchen", "sell": 13, "cost": 4,  "monthly_sales": 800,  "competition": 0.35},
        {"id": "pet_waste", "name": "Pet waste bags (refill)",      "category": "pet",     "sell": 22, "cost": 9,  "monthly_sales": 1200, "competition": 0.50},
        {"id": "of_pens",   "name": "Gel pens (bulk pack)",         "category": "office",  "sell": 26, "cost": 8,  "monthly_sales": 200,  "competition": 0.40},
        {"id": "kt_filter", "name": "Replacement water filters",    "category": "kitchen", "sell": 19, "cost": 6,  "monthly_sales": 500,  "competition": 0.60},
        {"id": "hm_box",    "name": "Storage boxes (set)",          "category": "home",    "sell": 40, "cost": 18, "monthly_sales": 300,  "competition": 0.70},
        {"id": "hm_org",    "name": "Drawer organizer set",         "category": "home",    "sell": 25, "cost": 7,  "monthly_sales": 900,  "competition": 0.85},
        {"id": "kt_chop",   "name": "Vegetable chopper",            "category": "kitchen", "sell": 24, "cost": 6,  "monthly_sales": 1500, "competition": 0.90},
        {"id": "pet_bowl",  "name": "Slow-feeder dog bowl",         "category": "pet",     "sell": 18, "cost": 5,  "monthly_sales": 700,  "competition": 0.60},
        {"id": "ft_band",   "name": "Resistance bands set",         "category": "fitness", "sell": 20, "cost": 4,  "monthly_sales": 1100, "competition": 0.88},
    ]


class MarketFeed(DataFeed):
    def __init__(self, rows):
        self.rows = rows
    def candidates(self):
        return [dict(r) for r in self.rows]


# 🧠 BRAIN — edge = ROI after fees + the advantage YOUR profile brings to this category.
class ScoutEdge(EdgeModel):
    def __init__(self, profile, fee_model: FeeModel = AMAZON_FBA):
        self.profile, self.fee_model = profile, fee_model

    def fair(self, it):
        return 1.0

    def mine(self, it):
        roi = _fees_for(it, self.fee_model).roi(it["sell"], it["cost"])
        fit = self.profile.fit(it)
        it["_roi"], it["_fit"] = roi, fit
        return 1.0 + roi + fit          # edge = roi + personal fit


# ❤️ HEART — gates tuned to the operator's appetite; only pursue real demand.
class ScoutRisk(Risk):
    def __init__(self, profile):
        r = profile.risk()
        super().__init__(profile.capital, min_edge=r["min_edge"], max_per=r["max_per"])
        self.min_monthly = profile.min_monthly

    def kelly(self, it, edge):
        return edge

    def stake(self, it, edge):
        if it.get("monthly_sales", 0) < self.min_monthly:
            return 0.0
        return round(self.max_per * self.bankroll, 2)   # a notional test commitment


# 👁️ EYES — read the competitive regime; learn which regimes actually pay.
class ScoutEyes(LearningEyes):
    def detect(self, it):
        c = it.get("competition", 0.5)
        pats = [{"name": "niche:" + it.get("category", "?"), "dir": 1}]
        if c >= 0.75:
            pats.append({"name": "leaders-dominate", "dir": -1})
        elif c <= 0.35:
            pats.append({"name": "open-lane", "dir": 1})
        return pats


# ✋ HANDS — surface the opportunity with its personalised read.
class ScoutExec(Execution):
    def place(self, it, stake, live=False):
        regime = "leaders" if it.get("competition", 0) >= 0.75 else ("OPEN" if it.get("competition", 1) <= 0.35 else "mixed")
        print("    🧭 PURSUE %-28s ROI %3.0f%% +fit %2.0f%% · %5.0f/mo · comp %3.0f%% [%s]"
              % (it["name"], it["_roi"] * 100, it["_fit"] * 100,
                 it.get("monthly_sales", 0), it.get("competition", 0) * 100, regime))


def landscape(rows, profile, fee_model: FeeModel = AMAZON_FBA):
    """Per-category map: how crowded, how much demand, base ROI, and your fit — ranked by
    (ROI + your advantage) so the lanes you can actually win float to the top."""
    by = {}
    for it in rows:
        cat = it.get("category", "?")
        roi = _fees_for(it, fee_model).roi(it["sell"], it["cost"])
        d = by.setdefault(cat, {"n": 0, "comp": 0.0, "dem": 0.0, "roi": 0.0})
        d["n"] += 1
        d["comp"] += it.get("competition", 0)
        d["dem"] += it.get("monthly_sales", 0)
        d["roi"] += roi
    out = []
    for cat, d in by.items():
        n = d["n"]
        out.append({"category": cat, "n": n, "competition": d["comp"] / n,
                    "demand": d["dem"] / n, "roi": d["roi"] / n,
                    "fit": profile.advantages.get(cat, 0.0)})
    out.sort(key=lambda r: r["roi"] + r["fit"], reverse=True)
    return out


def build(rows, profile, fee_model: FeeModel = AMAZON_FBA, journal=None) -> Machine:
    return Machine(MarketFeed(rows), ScoutEdge(profile, fee_model), ScoutRisk(profile),
                   ScoutEyes(), ScoutExec(), name="scout", journal=journal)
