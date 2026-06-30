#!/usr/bin/env python3
"""
arbitrage.py — buy low, sell high, on live data.

Two flavours, one math:
  • TEMPORAL (live today via Keepa): a product's price swings around its own 90-day average.
    When it's trading well BELOW that average — near its historical low — that's the moment to
    source/stock cheap and sell into the recovery. The dip IS the edge.
  • CROSS-CHANNEL (pluggable): the same product priced differently on two channels (Amazon vs
    Walmart/eBay/Shopify). Buy on the cheap one, sell on the dear one. Add a PriceSource and
    `cross_channel` lights up — the temporal math below is the same shape.

The pure functions here take plain numbers, so they unit-test without the network.
"""
from __future__ import annotations

from dataclasses import dataclass


def _clamp(x):
    return max(0.0, min(1.0, x))


@dataclass
class ArbSignal:
    current: float
    avg: float
    low: float
    high: float
    dip: float       # (avg - current) / avg : how far below its own norm right now (>0 = cheap)
    spread: float    # (high - low) / avg : how much room the price swings through
    edge: float      # 0..1 fused arbitrage strength
    verdict: str     # BUY THE DIP | below average | volatile (watch) | stable


def signal(points) -> "ArbSignal | None":
    """Score a temporal arbitrage from {current, avg, min, max} prices."""
    cur, avg = points.get("current"), points.get("avg")
    lo, hi = points.get("min"), points.get("max")
    if not cur or not avg or avg <= 0:
        return None
    dip = (avg - cur) / avg
    spread = ((hi - lo) / avg) if (hi and lo and avg) else 0.0
    edge = _clamp(max(dip, 0.0) / 0.20) * 0.7 + _clamp(spread / 0.50) * 0.3   # 20% dip or 50% swing = strong

    if lo and cur <= lo * 1.05 and dip >= 0.10:
        verdict = "BUY THE DIP"            # near the historical floor AND cheap vs norm
    elif dip >= 0.10:
        verdict = "below average"
    elif spread >= 0.30:
        verdict = "volatile (watch)"
    else:
        verdict = "stable"
    return ArbSignal(cur, avg, lo, hi, dip, spread, round(edge, 3), verdict)


# ── CROSS-CHANNEL (pluggable) ────────────────────────────────────────────────
class PriceSource:
    """Implement price(identifier) -> float for a channel (Amazon, Walmart, eBay, Shopify…)."""
    name = "channel"

    def price(self, identifier):
        raise NotImplementedError


def cross_channel(identifier, sources):
    """Best buy-low/sell-high across channels. Returns (buy_channel, buy, sell_channel, sell, edge)."""
    quotes = []
    for s in sources:
        try:
            p = s.price(identifier)
        except Exception:
            p = None
        if p and p > 0:
            quotes.append((s.name, p))
    if len(quotes) < 2:
        return None
    buy_ch, buy = min(quotes, key=lambda q: q[1])
    sell_ch, sell = max(quotes, key=lambda q: q[1])
    edge = _clamp(((sell - buy) / sell) / 0.30)        # 30% gross gap = full edge
    return {"buy_channel": buy_ch, "buy": buy, "sell_channel": sell_ch,
            "sell": sell, "edge": round(edge, 3)}
