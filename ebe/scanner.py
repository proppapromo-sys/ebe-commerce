#!/usr/bin/env python3
"""
scanner.py — COMB THE MARKET. Sweep many categories on Keepa in one run, score every
product through the true-edge + best-channel engine, de-dupe, and surface the best deals
ranked — so the opportunities come to you instead of you pasting listings one by one.

The supplier/cost side has no public API, so cost is still your RFQ quote; this combs the
DEMAND side (price, sales, competition) and tells you what's worth quoting on.

  from ebe.scanner import scan      # fetch_fn is injected (KeepaClient discover in the CLI)
"""
from __future__ import annotations

from .channels import best_channel
from .edges import score


def scan(fetch_fn, categories, profile=None, learned=None, limit=10, **filters):
    """Comb each category via fetch_fn(category=..., **filters) -> [item dicts].
    Returns the best opportunities, de-duped by id, ranked by deal score."""
    seen = {}
    for cat in categories:
        try:
            rows = fetch_fn(category=cat, **filters) or []
        except Exception:
            rows = []
        for r in rows:
            item = r.as_item() if hasattr(r, "as_item") else dict(r)
            item.setdefault("category", cat)
            key = item.get("id") or item.get("name")
            if key and key not in seen:
                seen[key] = item

    deals = []
    for item in seen.values():
        best = best_channel(item, profile, learned)
        e = score(item, profile, learned=learned)
        if not best:                                  # loses money on every channel → skip
            continue
        ms = item.get("monthly_sales", 0) or 0
        deal = e.composite * best["margin"] * ms      # edge × margin × demand = opportunity
        deals.append({
            "name": item.get("name", "?"), "id": item.get("id"),
            "category": item.get("category"), "cost": item.get("cost", 0),
            "sell": item.get("sell", 0), "monthly_sales": ms,
            "best_channel": best["channel"], "margin": best["margin"],
            "edge": e.composite, "verdict": e.verdict,
            "monthly_profit": round(best["net_unit"] * ms, 0), "deal_score": round(deal, 3),
        })
    deals.sort(key=lambda d: -d["deal_score"])
    return deals[:limit]
