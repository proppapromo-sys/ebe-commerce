#!/usr/bin/env python3
"""
alerts.py — WHAT NEEDS YOU. EBE Orb sweeps the whole operation and surfaces the handful
of things worth a human's attention right now, ranked by urgency: SKUs about to stock out,
products priced below a safe margin, what's under the reorder line, and your best seller.
Deterministic — no AI, no network — so it's instant and always available.

  from ebe.store import Store
  from ebe.alerts import scan, render_text
  print(render_text(scan(Store("ebe.db"), profile="hookah")))
"""
from __future__ import annotations

LEVELS = {"critical": 0, "warn": 1, "info": 2}
_ICON = {"critical": "🔴", "warn": "🟠", "info": "🔵"}


def _a(level, kind, message, action="", sku=None):
    return {"level": level, "kind": kind, "message": message, "action": action, "sku": sku}


def scan(store, profile="generic", fee=None) -> list:
    """Return a ranked list of alerts (most urgent first)."""
    from .fees import AMAZON_FBA
    from . import autobuy, repricer
    from . import pnl as pnlmod
    from .store import product_as_item
    fee = fee or AMAZON_FBA
    products = store.products()
    alerts = []

    for p in products:
        item = product_as_item(p)
        oh = item["on_hand"]
        daily = item["monthly_sales"] / 30.0
        lead = item.get("lead_time_days") or 21
        # about to stock out before a reorder could land
        if oh > 0 and daily > 0:
            cover = oh / daily
            if cover < lead:
                alerts.append(_a("critical", "stockout",
                                 "%s runs out in ~%.0fd (lead %dd)" % (item["name"][:24], cover, lead),
                                 "reorder now: python -m ebe rebuy", item["sku"]))
        # priced below the margin floor
        sell, cost = p.get("sell") or 0, p.get("cost") or 0
        if sell > 0 and cost > 0:
            floor = repricer.floor_price(cost, fee)
            if sell < floor - 1e-9:
                alerts.append(_a("warn", "below_floor",
                                 "%s at $%.2f is below safe floor $%.2f" % (item["name"][:24], sell, floor),
                                 "raise price or cut cost", item["sku"]))

    # under the reorder line (portfolio view)
    props = autobuy.plan(store)
    if props:
        cash = sum(x["cash"] for x in props)
        alerts.append(_a("warn", "reorder",
                         "%d SKU(s) under the reorder line — $%.0f to restock" % (len(props), cash),
                         "python -m ebe rebuy"))

    # best seller worth protecting (last 30 days of recorded sales)
    pl = pnlmod.compute(store, days=30)
    if pl["rows"]:
        top = pl["rows"][0]
        alerts.append(_a("info", "top_seller",
                         "%s is your top seller — %d sold, $%.0f gross (30d)"
                         % (top["name"][:24], top["units"], top["gross"]),
                         "keep it in stock", top["sku"]))

    alerts.sort(key=lambda x: LEVELS.get(x["level"], 9))
    return alerts


def summarize(alerts) -> dict:
    return {"total": len(alerts),
            "critical": sum(1 for a in alerts if a["level"] == "critical"),
            "warn": sum(1 for a in alerts if a["level"] == "warn"),
            "info": sum(1 for a in alerts if a["level"] == "info")}


def render_text(alerts) -> str:
    L = ["\n══ EBE COMMAND · ALERTS ══"]
    if not alerts:
        L.append("  🟢 All clear — nothing needs you right now.")
        return "\n".join(L)
    s = summarize(alerts)
    L.append("  %d alert(s) · %d critical · %d warning · %d info\n"
             % (s["total"], s["critical"], s["warn"], s["info"]))
    for a in alerts:
        line = "  %s %s" % (_ICON.get(a["level"], "•"), a["message"])
        if a["action"]:
            line += "  → %s" % a["action"]
        L.append(line)
    return "\n".join(L)
