#!/usr/bin/env python3
"""
forecast.py — see the cash coming. `command` tells you what to do TODAY; this tells you
what's coming so a restock never blindsides your bank balance.

For each SKU the engine already knows days-of-cover, supplier lead time, and reorder cost.
From that it projects WHEN each reorder must fire (cover runs down to the lead-time buffer)
and HOW MUCH cash it needs — a forward calendar plus 7/30/60/90-day cash windows.
"""
from __future__ import annotations

from .branches.inventory import expand_variants


def cash_calendar(products, safety_days=10, target_cover_days=45):
    """Forward reorder schedule: [{id, name, days_until, qty, cash, cover}, ...] soonest first."""
    rows = []
    for it in expand_variants(products):
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


def windows(rows, horizons=(7, 30, 60, 90)):
    """Cumulative cash needed within each horizon (days)."""
    return {h: round(sum(r["cash"] for r in rows if r["days_until"] <= h), 2) for h in horizons}
