#!/usr/bin/env python3
"""
shrinkage.py — DON'T BLEED INVENTORY. Two leaks the engine watches:

  stockout risk  — a SKU whose days-of-cover is shorter than its supplier lead time
                   will run dry before a re-buy can land. Catch it before the shelf is empty.
  shrinkage      — a physical count that comes up short of what the system expected is
                   theft, waste, spoilage, or miscount. Value it, rank it, stop it.

  from ebe.store import Store
  from ebe.shrinkage import stockout_risk, record_count, shrinkage_report
"""
from __future__ import annotations

from .store import product_as_item


def days_left(item):
    daily = (item.get("monthly_sales") or 0) / 30.0
    return (item["on_hand"] / daily) if daily > 0 else float("inf")


def stockout_risk(store, safety_days=3):
    """SKUs that will run dry before replenishment (cover < lead time + safety)."""
    out = []
    for p in store.products():
        item = product_as_item(p)
        daily = (item.get("monthly_sales") or 0) / 30.0
        if daily <= 0:
            continue
        cover = days_left(item)
        threshold = (item.get("lead_time_days") or 21) + safety_days
        if cover <= threshold:
            out.append({
                "sku": item["sku"], "name": item["name"], "on_hand": item["on_hand"],
                "daily": round(daily, 1), "days_left": round(cover, 1),
                "lead_time": item.get("lead_time_days") or 21,
                "stockout": cover < (item.get("lead_time_days") or 21),
                "shortfall_days": round(threshold - cover, 1),
            })
    out.sort(key=lambda x: x["days_left"])
    return out


def record_count(store, sku, counted):
    """Reconcile a physical count; return the variance with its $ value (shrinkage if negative)."""
    res = store.record_count(sku, counted)
    if res:
        res["value"] = round(min(0, res["variance"]) * res["cost"], 2)   # ≤ 0 = $ lost
    return res


def shrinkage_report(store, limit=500):
    """Aggregate every shortfall from physical counts: units lost and $ value, by SKU."""
    costs = {p["sku"]: (p.get("cost") or 0) for p in store.products()}
    names = {p["sku"]: p["name"] for p in store.products()}
    by_sku = {}
    counts = 0
    for e in store.events(limit=limit):
        if e["kind"] != "count" or (e.get("qty") or 0) >= 0:
            continue                                  # only shortfalls (negative variance)
        counts += 1
        sku = e["sku"]
        b = by_sku.setdefault(sku, {"sku": sku, "name": names.get(sku, sku), "units": 0, "value": 0.0})
        b["units"] += -e["qty"]
        b["value"] += round(-e["qty"] * costs.get(sku, 0), 2)
    rows = sorted(by_sku.values(), key=lambda x: -x["value"])
    return {
        "events": counts,
        "units_lost": sum(r["units"] for r in rows),
        "value_lost": round(sum(r["value"] for r in rows), 2),
        "by_sku": rows,
    }


def summarize(store):
    risk = stockout_risk(store)
    shrink = shrinkage_report(store)
    return {
        "stockout_count": sum(1 for r in risk if r["stockout"]),
        "at_risk": len(risk),
        "risk": risk,
        "shrink_value": shrink["value_lost"],
        "shrink_units": shrink["units_lost"],
        "shrink": shrink,
    }
