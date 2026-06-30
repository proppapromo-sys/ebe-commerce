#!/usr/bin/env python3
"""
membership.py — EBE MEMBER TIERS. A client's status by monthly REVENUE (real recorded
sales), from Launch → Bronze → Silver → Gold → Platinum → Diamond (Elite). Drives
retention (nobody wants to drop a tier) and motivation (a bar to the next one).

  from ebe.store import Store
  from ebe.membership import status, render_text
  print(render_text(status(Store("ebe.db"))))
"""
from __future__ import annotations

# Tiers by trailing monthly revenue ($). 'launch' is pre-first-sale.
TIERS = [
    {"key": "launch",   "name": "Launch",   "icon": "🚀", "min": 0,      "perks": "Get your first sale"},
    {"key": "bronze",   "name": "Bronze",   "icon": "🥉", "min": 1,      "perks": "Core EBE · member badge"},
    {"key": "silver",   "name": "Silver",   "icon": "🥈", "min": 1000,   "perks": "Extra channel · email receipts"},
    {"key": "gold",     "name": "Gold",     "icon": "🥇", "min": 5000,   "perks": "AI Orb reports · priority sync"},
    {"key": "platinum", "name": "Platinum", "icon": "💎", "min": 25000,  "perks": "Lower sub fee · multi-channel autopilot"},
    {"key": "diamond",  "name": "Diamond",  "icon": "👑", "min": 100000, "perks": "Lowest fee · white-glove · Elite status"},
]


def tier_for(revenue):
    """The highest tier whose threshold the revenue clears."""
    revenue = revenue or 0
    cur = TIERS[0]
    for t in TIERS:
        if revenue >= t["min"]:
            cur = t
    return cur


def next_tier(tier):
    """The tier above `tier`, or None if already Diamond."""
    for i, t in enumerate(TIERS):
        if t["key"] == tier["key"]:
            return TIERS[i + 1] if i + 1 < len(TIERS) else None
    return None


def status(store, days=30):
    """Compute the client's tier + progress from their recorded revenue (last `days`)."""
    from . import pnl as pnlmod
    revenue = pnlmod.compute(store, days=days)["totals"]["revenue"]
    cur = tier_for(revenue)
    nxt = next_tier(cur)
    if nxt:
        span = nxt["min"] - cur["min"]
        progress = max(0.0, min(1.0, (revenue - cur["min"]) / span)) if span else 1.0
        to_next = max(0.0, nxt["min"] - revenue)
    else:
        progress, to_next = 1.0, 0.0
    return {"revenue": round(revenue, 2), "days": days, "tier": cur,
            "next": nxt, "progress": progress, "to_next": round(to_next, 2)}


def render_text(s):
    t = s["tier"]
    L = ["\n══ EBE COMMAND · MEMBERSHIP ══"]
    L.append("  %s  %s MEMBER  ·  $%s revenue (last %dd)"
             % (t["icon"], t["name"].upper(), "{:,.0f}".format(s["revenue"]), s["days"]))
    if s["next"]:
        n = s["next"]
        fill = int(round(s["progress"] * 20))
        L.append("  [%s%s] %.0f%% to %s %s — $%s to go"
                 % ("█" * fill, "·" * (20 - fill), s["progress"] * 100,
                    n["icon"], n["name"], "{:,.0f}".format(s["to_next"])))
    else:
        L.append("  👑 Top tier — you're Elite.")
    L.append("\n  Tiers (monthly revenue):")
    for ti in TIERS[1:]:
        mark = "→" if ti["key"] == t["key"] else " "
        L.append("  %s %s %-9s $%-9s %s"
                 % (mark, ti["icon"], ti["name"], "{:,.0f}+".format(ti["min"]), ti["perks"]))
    return "\n".join(L)
