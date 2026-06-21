#!/usr/bin/env python3
"""
pnl.py — REALIZED PROFIT. Reads the sales EBE has recorded (from `sales` order pulls,
the `sell` command, bundle sales) and turns them into a profit-and-loss picture:
units, revenue, COGS, and gross profit per SKU and overall. Computed at the product's
current cost/sell — the honest "what did selling this actually earn" view.

  from ebe.store import Store
  from ebe.pnl import compute, render_text
  print(render_text(compute(Store("ebe.db"), days=30)))
"""
from __future__ import annotations

import time


def compute(store, days=None) -> dict:
    """Aggregate recorded sales into a P&L. days=None = all time; else the last N days."""
    since = (time.time() - days * 86400) if days else None
    by_sku = {}
    for e in store.sale_events(since):
        sku = e.get("sku")
        units = -(e.get("qty") or 0)            # sales are logged as negative qty
        if not sku or units <= 0:
            continue
        p = store.product(sku)
        if not p:
            continue
        cost, sell = p.get("cost") or 0, p.get("sell") or 0
        row = by_sku.setdefault(sku, {"sku": sku, "name": p.get("name") or sku,
                                      "units": 0, "revenue": 0.0, "cogs": 0.0})
        row["units"] += units
        row["revenue"] += units * sell
        row["cogs"] += units * cost

    rows = []
    for r in by_sku.values():
        r["gross"] = round(r["revenue"] - r["cogs"], 2)
        r["margin"] = (r["gross"] / r["revenue"]) if r["revenue"] else 0.0
        r["revenue"] = round(r["revenue"], 2)
        r["cogs"] = round(r["cogs"], 2)
        rows.append(r)
    rows.sort(key=lambda x: -x["gross"])

    rev = round(sum(r["revenue"] for r in rows), 2)
    cogs = round(sum(r["cogs"] for r in rows), 2)
    totals = {"units": sum(r["units"] for r in rows), "revenue": rev, "cogs": cogs,
              "gross": round(rev - cogs, 2), "margin": ((rev - cogs) / rev) if rev else 0.0,
              "skus": len(rows)}
    return {"rows": rows, "totals": totals, "days": days}


def render_text(p) -> str:
    t = p["totals"]
    win = ("last %d days" % p["days"]) if p["days"] else "all time"
    L = ["\n══ EBE COMMAND · P&L (%s) ══" % win]
    if not p["rows"]:
        L.append("  No recorded sales yet — pull them with `python -m ebe sales --channel shopify`,")
        L.append("  or log one with `python -m ebe sell --id SKU --units N`.")
        return "\n".join(L)
    L.append("  %-26s %6s %10s %10s %10s %6s" % ("product", "units", "revenue", "COGS", "gross", "marg"))
    for r in p["rows"]:
        L.append("  %-26s %6d %10.2f %10.2f %10.2f %5.0f%%"
                 % (r["name"][:26], r["units"], r["revenue"], r["cogs"], r["gross"], r["margin"] * 100))
    L.append("  " + "-" * 70)
    L.append("  %-26s %6d %10.2f %10.2f %10.2f %5.0f%%"
             % ("TOTAL", t["units"], t["revenue"], t["cogs"], t["gross"], t["margin"] * 100))
    return "\n".join(L)
