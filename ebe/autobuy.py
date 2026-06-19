#!/usr/bin/env python3
"""
autobuy.py — THE RE-BUY ENGINE. Watches the database; raises a purchase order the
instant a SKU crosses its reorder line, sized to a cover target, never double-ordering.

It reuses the inventory branch's math (reorder point = demand over lead time + safety;
cover target = demand over the days you want to hold) so the engine and the dashboard
agree on every number. Heart still rules: a PO is only raised once stock is at/under the
reorder point, and only if there isn't already one in flight for that SKU.

Two honesty levels, chosen by `auto`:
    auto=False (default)  → status 'draft'  : the engine proposes, you one-click approve
    auto=True             → status 'ordered': hands-off (use only with a real supplier channel)

  from ebe.store import Store
  from ebe.autobuy import scan
  pos = scan(Store("ebe.db"))        # raises drafts for everything under the line
"""
from __future__ import annotations

from .branches.inventory import reorder_point, days_of_cover
from .store import Store, product_as_item


def needs_reorder(item, safety_days=10):
    """True once on-hand has fallen to or below the reorder point."""
    rp = reorder_point(item, safety_days=safety_days)
    return rp > 0 and item["on_hand"] <= rp


def cover_qty(item, target_cover_days=45):
    """Units to bring stock up to (target cover + lead time) of demand."""
    daily = item["monthly_sales"] / 30.0
    target = daily * (target_cover_days + item["lead_time_days"])
    return max(0, round(target - item["on_hand"]))


def plan(store: Store, safety_days=10, target_cover_days=45) -> list:
    """What the engine WOULD buy right now — pure read, writes nothing."""
    open_skus = store.open_skus()
    proposals = []
    for p in store.products():
        item = product_as_item(p)
        if item["sku"] in open_skus:
            continue
        if not needs_reorder(item, safety_days):
            continue
        qty = cover_qty(item, target_cover_days)
        if qty <= 0:
            continue
        rp = reorder_point(item, safety_days)
        proposals.append({
            "sku": item["sku"], "name": item["name"], "qty": qty,
            "unit_cost": item["cost"], "cash": round(qty * item["cost"], 2),
            "on_hand": item["on_hand"], "reorder_point": round(rp, 1),
            "cover_days": round(days_of_cover(item), 1), "supplier": item.get("supplier"),
            "reason": "cover %.0fd ≤ reorder point %.0f" % (days_of_cover(item), rp),
        })
    proposals.sort(key=lambda x: x["cover_days"])      # most urgent first
    return proposals


def raise_for(store: Store, sku, safety_days=10, target_cover_days=45, status="draft"):
    """Raise a single PO for one SKU from its current proposal. Returns the PO id or None."""
    for prop in plan(store, safety_days, target_cover_days):
        if prop["sku"] == sku:
            return store.create_po(prop["sku"], prop["qty"], prop["unit_cost"],
                                   reason=prop["reason"], supplier=prop["supplier"], status=status)
    return None


def scan(store: Store, safety_days=10, target_cover_days=45, auto=False, budget=None) -> list:
    """Raise purchase orders for everything under the line. Returns the POs created.

    budget caps total cash committed this scan (most-urgent-first); None = uncapped.
    """
    status = "ordered" if auto else "draft"
    spent, raised = 0.0, []
    for prop in plan(store, safety_days, target_cover_days):
        if budget is not None and spent + prop["cash"] > budget:
            continue
        po_id = store.create_po(prop["sku"], prop["qty"], prop["unit_cost"],
                                reason=prop["reason"], supplier=prop["supplier"], status=status)
        spent += prop["cash"]
        raised.append(store.purchase_order(po_id))
    return raised
