#!/usr/bin/env python3
"""
engine.py — EBE Venue OS Phase 1: POS counts in → supplies consumed → "reorder?" out.

It REUSES the genome's restock organs (the same reorder-point brain the Amazon inventory
branch runs) — proof that one Universal Genome runs the venue, not just the marketplace.
The flow:

  POS sales ─explode BOM→ usage ─deplete stock→ days-of-cover ─restock brain→ "Reorder now?"
"""
from __future__ import annotations

import math

from ..genome import Machine, DataFeed, BlindEyes, Execution
from ..branches.inventory import RestockEdge, RestockRisk, days_of_cover
from .bom import explode_usage


class _ConsumableFeed(DataFeed):
    def __init__(self, items):
        self.items = items
    def candidates(self):
        return list(self.items)


class VenueReorderExec(Execution):
    """One-click reorder, rounded up to whole cases."""
    def place(self, item, stake, live=False):
        units = int(stake)
        if units <= 0:
            return
        pack = item.get("pack_size", 1) or 1
        cases = math.ceil(units / pack)
        order_units = cases * pack
        print("    🛒 REORDER %-26s %5d units (%d × %d-pack) · $%-5.0f · cover %2.0fd  [one-click ✅]"
              % (item["name"], order_units, cases, pack, order_units * item["cost"], days_of_cover(item)))


def to_restock_items(usage, consumables, period_days=30):
    """Map consumable usage into the dict the restock brain reads (usage = its 'demand')."""
    items = []
    for cid, used in usage.items():
        c = consumables.get(cid)
        if not c:
            continue
        monthly = used * 30.0 / period_days
        items.append({
            "id": cid, "name": c.name, "category": c.category, "on_hand": c.on_hand,
            "monthly_sales": monthly, "lead_time_days": c.lead_time_days,
            "cost": c.unit_cost, "pack_size": c.pack_size,
        })
    return items


def run(sales, menu, consumables, period_days=30, place=True):
    """Full Phase-1 pass: consumption report + spend + auto-reorder. Returns reorder tickets."""
    usage = explode_usage(sales, menu)
    items = to_restock_items(usage, consumables, period_days)

    sold = " · ".join("%d %s" % (n, menu[m].name if m in menu else m) for m, n in sales.items())
    print("EBE VENUE OS — consumption from: %s  (over %d days)\n" % (sold, period_days))

    monthly_spend = 0.0
    for it in sorted(items, key=lambda x: -x["monthly_sales"] * x["cost"]):
        spend = it["monthly_sales"] * it["cost"]
        monthly_spend += spend
        print("  %-26s %7.0f used/mo · %3.0fd cover · $%6.0f/mo" %
              (it["name"], it["monthly_sales"], days_of_cover(it), spend))
    print("\n  monthly supply spend ≈ $%.0f\n" % monthly_spend)

    print("⚠️  Running low → reorder?")
    m = Machine(_ConsumableFeed(items), RestockEdge(), RestockRisk(), BlindEyes(),
                VenueReorderExec(), name="venue")
    tickets = m.cycle(place=place)
    if not tickets:
        print("  (everything well-stocked)")
    return tickets
