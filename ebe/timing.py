#!/usr/bin/env python3
"""
timing.py — momentum, not guesswork. Is a product RISING or FADING right now?

Keepa tracks a product's sales rank over time (lower rank = selling more). A product whose
current rank sits BELOW its own 90-day average is accelerating — demand is building, the wave
is forming. One trading above its average is fading. Riding the rise beats fighting the fall;
this turns the true-edge engine's `timing` angle from a flat guess into a live read.
"""
from __future__ import annotations


def _clamp(x):
    return max(0.0, min(1.0, x))


def momentum(rank_points):
    """{current_rank, avg_rank} (lower is better) -> (score 0..1, label).
    score > 0.5 = rising (current better than its average), < 0.5 = fading."""
    cur, avg = rank_points.get("current_rank"), rank_points.get("avg_rank")
    if not cur or not avg or avg <= 0:
        return (0.5, "unknown")
    rel = (avg - cur) / avg                 # >0: current rank lower(better) than average -> rising
    score = _clamp(0.5 + rel)
    if rel >= 0.15:
        label = "rising"
    elif rel <= -0.15:
        label = "fading"
    else:
        label = "flat"
    return (round(score, 3), label)
