#!/usr/bin/env python3
"""
plans.py — the subscription tier model (from TIER_SYSTEM_SPEC). Plans, prices, seat caps,
and a feature→minimum-plan matrix, with the gating helpers the UI needs. Pure data + logic.

  starter $49 (1 seat) → growth $149 (3) → pro $349 (7) → agency $999 (20)
"""
from __future__ import annotations

PLANS = [
    {"key": "starter", "name": "Starter", "monthly": 49,  "seats": 1,  "locations": 1,  "media": 5},
    {"key": "growth",  "name": "Growth",  "monthly": 149, "seats": 3,  "locations": 3,  "media": 25},
    {"key": "pro",     "name": "Pro",     "monthly": 349, "seats": 7,  "locations": 7,  "media": 100},
    {"key": "agency",  "name": "Agency",  "monthly": 999, "seats": 20, "locations": 20, "media": 500},
]
ORDER = [p["key"] for p in PLANS]
_BY_KEY = {p["key"]: p for p in PLANS}

# feature flag → the cheapest plan that unlocks it
FEATURES = {
    "catalog":          "starter", "restock": "starter", "pricing": "starter",
    "profit":           "starter", "one_channel": "starter", "membership": "starter",
    "settings":         "starter", "team_users": "starter", "alerts": "starter",
    "multi_channel":    "growth",  "autopilot": "growth",  "ai_reports": "growth",
    "discover":         "growth",  "ai_descriptions": "growth",
    "priority_sync":    "pro",     "amazon_publish": "pro",
    "multi_account":    "agency",  "white_label": "agency",
}


def plan(key):
    """The plan dict for a key (defaults to starter on unknown)."""
    return _BY_KEY.get((key or "").lower(), _BY_KEY["starter"])


def rank(key):
    """0..3 position of a plan, low→high (unknown → 0)."""
    k = (key or "").lower()
    return ORDER.index(k) if k in ORDER else 0


def seat_cap(key):
    return plan(key)["seats"]


def location_cap(key):
    return plan(key)["locations"]


def media_cap(key):
    return plan(key)["media"]


def includes(key, feature):
    """Does this plan unlock the feature?"""
    need = FEATURES.get(feature)
    if need is None:
        return True                      # unknown feature → not gated
    return rank(key) >= rank(need)


def upgrade_for(feature):
    """Cheapest plan key that unlocks the feature (for 'Upgrade to X' nudges), or None."""
    return FEATURES.get(feature)


def next_seat_upgrade(key):
    """The next plan with a higher seat cap, or None if already at the top."""
    cur = seat_cap(key)
    for p in PLANS:
        if p["seats"] > cur:
            return p["key"]
    return None
