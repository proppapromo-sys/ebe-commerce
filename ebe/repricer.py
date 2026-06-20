#!/usr/bin/env python3
"""
repricer.py — PRICING OPTIMIZATION. Pricing that reacts to the live market while it
defends a hard margin floor. Static "best price" leaves money on the table when rivals
move; this positions each SKU against real competitor prices and never sells below the
price that earns your minimum ROI after fees.

  floor   = the lowest price that still clears your floor ROI (after all fees)
  recommend(item, competitors, fee) → where to sit: undercut · match · premium, but ≥ floor

  from ebe.repricer import recommend
  recommend({"cost":7,"sell":24}, [21.99, 22.50], AMAZON_FBA, strategy="undercut")
"""
from __future__ import annotations

import math


def floor_price(cost, fee, floor_roi=0.30):
    """Lowest sell price that still earns floor_roi after fees (ROI rises with price)."""
    lo, hi = 0.01, max(cost * 12, 10.0)
    if fee.roi(hi, cost) < floor_roi:           # even a high price can't clear the floor
        return math.ceil(hi * 100) / 100.0
    for _ in range(60):                         # bisection — ROI is monotonic in price
        mid = (lo + hi) / 2.0
        if fee.roi(mid, cost) < floor_roi:
            lo = mid
        else:
            hi = mid
    return math.ceil(hi * 100) / 100.0          # round UP to the cent so the floor always holds


def recommend(item, competitors, fee, floor_roi=0.30, strategy="undercut", step=0.01):
    """Where to price this SKU. strategy: undercut | match | premium. Never below floor."""
    cost = item.get("cost", 0) or 0
    current = item.get("sell", 0) or 0
    floor = floor_price(cost, fee, floor_roi)
    comps = sorted(p for p in (competitors or []) if p and p > 0)

    if not comps:
        rec = max(current, floor)
        reason = "no live competitors — hold above floor $%.2f" % floor
    else:
        low, median = comps[0], comps[len(comps) // 2]
        if strategy == "match":
            target = low
        elif strategy == "premium":
            target = median                      # sit at the middle of the market, not the floor
        else:                                    # undercut
            target = low - step
        rec = round(max(target, floor), 2)
        if strategy == "undercut" and rec >= low:
            reason = "can't beat market low $%.2f without breaking floor $%.2f — hold at floor" % (low, floor)
        else:
            reason = "%s · market low $%.2f, median $%.2f, floor $%.2f" % (strategy, low, median, floor)

    move = round(rec - current, 2)
    return {"recommended": rec, "floor": floor, "current": current,
            "market_low": comps[0] if comps else None,
            "roi": fee.roi(rec, cost), "margin": fee.margin(rec, cost),
            "move": move, "at_floor": rec <= floor + 1e-9, "reason": reason}


def reprice_catalog(products, prices_by_sku, fee, floor_roi=0.30, strategy="undercut"):
    """Recommend a price per stored product given {sku: [competitor prices]}. Sorted by upside."""
    out = []
    for p in products:
        comps = prices_by_sku.get(p["sku"], [])
        rec = recommend(p, comps, fee, floor_roi=floor_roi, strategy=strategy)
        rec["sku"], rec["name"] = p["sku"], p.get("name", p["sku"])
        out.append(rec)
    out.sort(key=lambda r: -abs(r["move"]))
    return out
