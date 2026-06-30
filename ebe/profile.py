#!/usr/bin/env python3
"""
profile.py — WHO YOU ARE. The engine is the same for everyone; the answers shouldn't be.

A Profile personalises every branch to one operator: how much capital they'll risk, how
aggressive they are, which categories they care about, the real-world ADVANTAGES they bring
(a hookah-lounge owner sources hookah supplies cheaper and knows the niche cold), and their
goals. Same genome, different lens — so a hookah operator and a general seller get different
shortlists from identical data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Risk appetite → the Heart's gates. Higher appetite = lower edge bar, bigger per-bet, more exposure.
APPETITES = {
    "conservative": {"min_edge": 0.45, "max_per": 0.10, "exposure": 0.40},
    "balanced":     {"min_edge": 0.30, "max_per": 0.20, "exposure": 0.60},
    "aggressive":   {"min_edge": 0.20, "max_per": 0.30, "exposure": 0.90},
}


@dataclass
class Profile:
    name: str
    capital: float = 2000.0
    appetite: str = "balanced"           # conservative | balanced | aggressive
    fee_model: str = "amazon-fba"
    categories: list = field(default_factory=list)   # what you focus on
    advantages: dict = field(default_factory=dict)   # category -> edge bonus you bring (0..1)
    goals: list = field(default_factory=list)        # e.g. ["recurring", "high-margin"]
    min_monthly: int = 100               # ignore markets thinner than this

    def risk(self) -> dict:
        return APPETITES.get(self.appetite, APPETITES["balanced"])

    def fit(self, item) -> float:
        """Your personal edge bonus for this item's category (0 if it's not your turf)."""
        return float(self.advantages.get(item.get("category"), 0.0))


# A few starting profiles. Clone and tune one to a real operator.
PROFILES = {
    "hookah": Profile(
        "Hookah-lounge operator", capital=3000, appetite="balanced",
        categories=["hookah", "bar", "takeout"],
        advantages={"hookah": 0.30, "bar": 0.15, "takeout": 0.10},
        goals=["recurring", "high-margin"]),
    "generic": Profile("General seller", capital=2000, appetite="balanced"),
    "cautious": Profile("Cautious starter", capital=1000, appetite="conservative"),
    "aggressive": Profile("Aggressive scaler", capital=8000, appetite="aggressive"),
}
