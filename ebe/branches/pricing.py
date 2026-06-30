#!/usr/bin/env python3
"""
pricing.py — BRANCH 2: REPRICE FOR MAXIMUM PROFIT-AFTER-FEES.

Your list price is rarely your best price. Using a constant-elasticity demand curve,
this branch scans prices around your current one and finds the price that maximises
MONTHLY profit after every fee. Edge = how much better the best price is than today's.
Confirm-first: it proposes the move, it doesn't yank your price around on a whim.

  python -m ebe pricing
"""
from __future__ import annotations

from ..genome import EdgeModel, Risk, Execution, BlindEyes, Machine
from ..fees import FeeModel, AMAZON_FBA, MERCH_APPAREL


def _fees_for(item, default: FeeModel) -> FeeModel:
    return MERCH_APPAREL if item.get("category") == "apparel" or item.get("is_apparel") else default


def demand_at(price, ref_price, ref_qty, elasticity):
    """Constant-elasticity demand: qty = ref_qty · (price / ref_price)^(-elasticity)."""
    if ref_price <= 0 or price <= 0:
        return 0.0
    return ref_qty * (price / ref_price) ** (-elasticity)


def best_price(p, fm: FeeModel):
    """Scan a price grid; return (price, monthly_profit) that maximises profit after fees."""
    ref_price, ref_qty = p["sell"], max(p["monthly_sales"], 1e-9)
    lo, hi = max(p["cost"] * 1.05, ref_price * 0.5), ref_price * 2.0
    best = (ref_price, -1e18)
    steps = 60
    for i in range(steps + 1):
        price = lo + (hi - lo) * i / steps
        qty = demand_at(price, ref_price, ref_qty, p.get("elasticity", 1.5))
        profit = qty * fm.net_unit(price, p["cost"])
        if profit > best[1]:
            best = (round(price, 2), profit)
    return best


# 🧠 BRAIN — mine = profit at the optimal price; fair = profit at today's price.
class PricingEdge(EdgeModel):
    def __init__(self, fee_model: FeeModel = AMAZON_FBA):
        self.fee_model = fee_model

    def _profits(self, p):
        fm = _fees_for(p, self.fee_model)
        cur = max(p["monthly_sales"], 1e-9) * fm.net_unit(p["sell"], p["cost"])
        bp, bprofit = best_price(p, fm)
        p["_best_price"], p["_cur_profit"], p["_best_profit"] = bp, cur, bprofit
        return cur, bprofit

    def fair(self, p):
        return 1.0
    def mine(self, p):
        cur, best = self._profits(p)
        if cur <= 0:
            return 1.0 + (1.0 if best > 0 else 0.0)
        return 1.0 + best / cur          # edge = fractional profit uplift from repricing


# ❤️ HEART — only act on a meaningful uplift; "stake" = the monthly profit at risk of being left on the table.
class PricingRisk(Risk):
    def __init__(self, capital=10000, min_uplift=0.05, max_move=0.25):
        super().__init__(capital, min_edge=min_uplift, max_per=1.0)
        self.max_move = max_move         # never propose more than ±25% in one step

    def kelly(self, p, edge):
        return edge

    def stake(self, p, edge):
        return round(max(0.0, p.get("_best_profit", 0) - p.get("_cur_profit", 0)), 2)


# ✋ HANDS — propose the new price (capped to a sane single step).
class PricingExec(Execution):
    def __init__(self, max_move=0.25):
        self.max_move = max_move

    def place(self, p, stake, live=False):
        cur, target = p["sell"], p.get("_best_price", p["sell"])
        capped = min(max(target, cur * (1 - self.max_move)), cur * (1 + self.max_move))
        capped = round(capped, 2)
        arrow = "↑" if capped > cur else ("↓" if capped < cur else "→")
        tag = "" if live else "[dry-run] "
        print("    %s🏷️  REPRICE %-22s $%.2f %s $%.2f  (+$%.0f/mo profit)"
              % (tag, p["name"], cur, arrow, capped, stake))


def build(feed, fee_model: FeeModel = AMAZON_FBA, min_uplift=0.05) -> Machine:
    return Machine(feed, PricingEdge(fee_model), PricingRisk(min_uplift=min_uplift),
                   BlindEyes(), PricingExec(), name="pricing")
