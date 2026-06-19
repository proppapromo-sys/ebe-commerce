#!/usr/bin/env python3
"""
forecast.py — see the cash coming. `command` tells you what to do TODAY; this tells you
what's coming so a restock never blindsides your bank balance — for the store AND the venue.

For each SKU/consumable the engine knows days-of-cover, supplier lead time, and reorder cost.
From that it projects WHEN each reorder must fire and HOW MUCH cash it needs — a forward
calendar, 7/30/60/90-day cash windows, and (with --capital) a runway/solvency read.
"""
from __future__ import annotations

from .branches.inventory import expand_variants


def _calendar(items, safety_days=10, target_cover_days=45):
    """Core projection over plain item dicts {id,name,on_hand,monthly_sales,lead_time_days,cost}."""
    rows = []
    for it in items:
        daily = it.get("monthly_sales", 0) / 30.0
        if daily <= 0:
            continue
        cover = it["on_hand"] / daily
        must_reorder_at = it["lead_time_days"] + safety_days       # reorder when cover hits this
        days_until = max(0.0, cover - must_reorder_at)
        qty = round(daily * target_cover_days)                     # steady-state reorder size
        if qty <= 0:
            continue
        rows.append({
            "id": it["id"], "name": it["name"], "days_until": round(days_until, 1),
            "qty": int(qty), "cash": round(qty * it.get("cost", 0), 2), "cover": round(cover, 1),
        })
    rows.sort(key=lambda r: r["days_until"])
    return rows


def cash_calendar(products, **kw):
    """Store forward reorder schedule (per apparel variant)."""
    return _calendar(expand_variants(products), **kw)


def venue_calendar(sales, menu, consumables, period_days=30, **kw):
    """Venue supplies forward schedule: POS counts -> consumables -> run-out + reorder cash."""
    from .venue.bom import explode_usage
    from .venue.engine import to_restock_items
    items = to_restock_items(explode_usage(sales, menu), consumables, period_days)
    return _calendar(items, **kw)


def windows(rows, horizons=(7, 30, 60, 90)):
    """Cumulative cash needed within each horizon (days)."""
    return {h: round(sum(r["cash"] for r in rows if r["days_until"] <= h), 2) for h in horizons}


def runway(window_cash, capital):
    """Capital left after each horizon's cash need — negative means SHORT (can't cover it)."""
    return {h: round(capital - cash, 2) for h, cash in window_cash.items()}
