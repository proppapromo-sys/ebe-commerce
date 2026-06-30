#!/usr/bin/env python3
"""
inventory.py — BRANCH 3: RESTOCK BEFORE YOU STOCK OUT.

A stockout on Amazon is a double tax: lost sales now AND a bruised ranking that costs
you for weeks. This branch computes each SKU's reorder point (demand over the supplier
lead time + safety stock) and flags what's running hot. For apparel it works PER VARIANT
— "Large Black" can be on fire while "Small Red" rots.

Edge here is urgency: how far below the reorder point you've fallen.

  python -m ebe inventory
"""
from __future__ import annotations

from ..genome import DataFeed, EdgeModel, Risk, Execution, BlindEyes, Machine


def expand_variants(products) -> list:
    """Explode apparel products into one candidate per variant; simple products pass through."""
    out = []
    for p in products:
        item = p.as_item()
        if p.variants:
            for v in p.variants:
                out.append({
                    "id": "%s·%s" % (p.id, v.sku), "name": "%s %s" % (p.name, v.sku),
                    "on_hand": v.on_hand, "monthly_sales": v.monthly_sales,
                    "lead_time_days": p.lead_time_days, "cost": p.cost,
                })
        else:
            out.append({
                "id": p.id, "name": p.name, "on_hand": item["on_hand"],
                "monthly_sales": item["monthly_sales"], "lead_time_days": p.lead_time_days,
                "cost": p.cost,
            })
    return out


class VariantFeed(DataFeed):
    def __init__(self, products):
        self.products = products
    def candidates(self):
        return expand_variants(self.products)


def reorder_point(item, safety_days=10):
    daily = item["monthly_sales"] / 30.0
    return daily * (item["lead_time_days"] + safety_days)


def days_of_cover(item):
    daily = item["monthly_sales"] / 30.0
    return item["on_hand"] / daily if daily > 0 else float("inf")


# 🧠 BRAIN — edge = how far below the reorder point (0 = at it, 1 = fully out).
class RestockEdge(EdgeModel):
    def fair(self, item):
        return 0.0
    def mine(self, item):
        rp = reorder_point(item)
        if rp <= 0:
            return 0.0
        return max(0.0, (rp - item["on_hand"]) / rp)


# ❤️ HEART — act once you've crossed the reorder point; size = a cover-target order.
class RestockRisk(Risk):
    def __init__(self, urgency_gate=0.0, target_cover_days=45):
        super().__init__(bankroll=0, min_edge=max(urgency_gate, 1e-6), max_per=1.0)
        self.target_cover_days = target_cover_days

    def kelly(self, item, edge):
        return edge

    def stake(self, item, edge):
        daily = item["monthly_sales"] / 30.0
        target = daily * (self.target_cover_days + item["lead_time_days"])
        qty = max(0, round(target - item["on_hand"]))
        return float(qty)            # "stake" = units to reorder


# ✋ HANDS — raise the purchase order.
class RestockExec(Execution):
    def place(self, item, stake, live=False):
        units = int(stake)
        if units <= 0:
            return
        tag = "" if live else "[dry-run] "
        print("    %s🚚 REORDER %-24s %4d units  (cover %.0fd → reorder point %.0f, $%.0f cash)"
              % (tag, item["name"], units, days_of_cover(item), reorder_point(item), units * item["cost"]))


def build(products, urgency_gate=0.0) -> Machine:
    return Machine(VariantFeed(products), RestockEdge(), RestockRisk(urgency_gate),
                   BlindEyes(), RestockExec(), name="inventory")
