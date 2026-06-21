#!/usr/bin/env python3
"""
status.py — ONE SCREEN: is my shop actually running? Built for the operator who has
autopilot scheduled and just wants to glance and trust it. Pulls the live picture from
the database + .env: what's connected, when autopilot last ran, what's pending, and the
one thing (if anything) that needs a human.

  from ebe.store import Store
  from ebe.status import compose, render_text
  print(render_text(compose(Store("ebe.db"))))
"""
from __future__ import annotations

import time

# how stale an autopilot run can get before we flag it (a scheduled hourly job
# should never be older than this)
STALE_AFTER_HOURS = 3.0


def _ago(ts):
    """Human 'time since' for a unix ts — '12m ago', '3h ago', 'never'."""
    if not ts:
        return "never"
    secs = max(0, time.time() - ts)
    if secs < 90:
        return "just now"
    if secs < 3600:
        return "%dm ago" % (secs // 60)
    if secs < 86400:
        return "%dh ago" % (secs // 3600)
    return "%dd ago" % (secs // 86400)


def compose(store) -> dict:
    from . import autobuy, sync
    from .adapters import config

    products = store.products()
    drafts = store.purchase_orders("draft")
    ordered = store.purchase_orders("ordered")
    proposals = autobuy.plan(store) if products else []

    # what's actually wired up
    channels = []
    for name in ("amazon", "shopify"):
        keys = config.NEEDS.get(name, [])
        channels.append({"name": name, "connected": bool(keys) and not config.require(keys)})
    connected = [c["name"] for c in channels if c["connected"]]

    # autopilot freshness
    last = store.last_event("autopilot")
    last_ts = last["ts"] if last else None
    age_h = (time.time() - last_ts) / 3600.0 if last_ts else None
    if last_ts is None:
        health = "never_run"
    elif age_h is not None and age_h > STALE_AFTER_HOURS:
        health = "stale"
    else:
        health = "fresh"

    from . import brief as briefmod
    cash = briefmod.live_cash()

    # the one thing a human should know
    if not products:
        flag = "No catalog — load it: python -m ebe catalog --products data/products.csv"
    elif not connected:
        flag = "No channels connected — autopilot can't see live sales. See: python -m ebe connections"
    elif health == "never_run":
        flag = "Autopilot has never run — schedule it (see docs/RUN_LIVE.md) or: python -m ebe autopilot"
    elif health == "stale":
        flag = "Autopilot last ran %s — it may not be scheduled. Check your task." % _ago(last_ts)
    elif drafts:
        flag = "%d re-buy draft(s) waiting for approval — python -m ebe orders --status draft" % len(drafts)
    else:
        flag = "All green — autopilot is running and stock is covered."

    return dict(
        products=len(products),
        channels=channels, connected=connected,
        low=len(proposals),
        drafts=len(drafts), draft_value=round(sum(p["cash"] for p in drafts), 2),
        ordered=len(ordered), inbound_value=round(sum(p["cash"] for p in ordered), 2),
        last_run_ts=last_ts, last_run_ago=_ago(last_ts),
        last_run_note=(last or {}).get("note"), health=health,
        cash=cash, flag=flag,
    )


def render_text(s) -> str:
    icon = {"fresh": "🟢", "stale": "🟡", "never_run": "🔴"}.get(s["health"], "⚪")
    L = ["\n══ EBE COMMAND · STATUS ══"]
    L.append("%s AUTOPILOT  %s%s" % (
        icon, s["last_run_ago"],
        ("  ·  " + s["last_run_note"]) if s["last_run_note"] else ""))
    chans = ", ".join("%s%s" % ("✓" if c["connected"] else "✗", c["name"]) for c in s["channels"])
    L.append("🔌 CHANNELS   %s   (%d connected)" % (chans, len(s["connected"])))
    L.append("📦 CATALOG    %d SKU(s) · %d under the reorder line" % (s["products"], s["low"]))
    L.append("📝 PENDING    %d draft(s) $%.0f · %d inbound PO(s) $%.0f"
             % (s["drafts"], s["draft_value"], s["ordered"], s["inbound_value"]))
    if s.get("cash"):
        c = s["cash"]
        L.append("💰 CASH       $%.0f available · $%.0f revenue/30d" % (c["available"], c["revenue30"]))
    L.append("\n➡️  %s" % s["flag"])
    return "\n".join(L)
