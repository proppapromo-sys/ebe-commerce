#!/usr/bin/env python3
"""
channels.py — BEST CHANNEL, AUTOMATICALLY. Score one product across every channel at
once (Amazon FBA, Shopify, Etsy, apparel, local delivery) and name the winner — so you
never run `rank` three times again. The same product is a loss on FBA and a 60%-margin
winner local; this tells you which is which in one shot.

  from ebe.channels import compare, best_channel
"""
from __future__ import annotations

from .fees import PRESETS
from .edges import score


def compare(item, profile=None, learned=None) -> list:
    """Margin/verdict for `item` on every channel, best projected profit first."""
    ms = item.get("monthly_sales", 0) or 0
    rows = []
    for name, fee in PRESETS.items():
        e = score(item, profile, fee, learned=learned)
        net = fee.net_unit(item.get("sell", 0), item.get("cost", 0))
        rows.append({
            "channel": name, "net_unit": round(net, 2),
            "margin": fee.margin(item.get("sell", 0), item.get("cost", 0)),
            "roi": fee.roi(item.get("sell", 0), item.get("cost", 0)),
            "monthly_profit": round(net * ms, 0),
            "verdict": e.verdict, "composite": e.composite,
        })
    rows.sort(key=lambda r: (-r["monthly_profit"], -r["margin"]))
    return rows


def best_channel(item, profile=None, learned=None):
    """The single recommended channel (highest positive projected profit), or None."""
    rows = [r for r in compare(item, profile, learned) if r["net_unit"] > 0]
    return rows[0] if rows else None
