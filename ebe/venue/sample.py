#!/usr/bin/env python3
"""
sample.py — a sample venue (restaurant + bar + hookah lounge) so Venue OS runs out of
the box. Swap these for YOUR menu's recipes, YOUR supplies, and YOUR POS counts.
"""
from __future__ import annotations

from .bom import Consumable, MenuItem


def sample_menu():
    """What you sell, and the supplies each sale burns."""
    return {
        "drink":   MenuItem("drink",   "Cocktail / soft drink",
                            {"cup_clear": 1, "straw": 1, "napkin": 2}),
        "hookah":  MenuItem("hookah",  "Hookah session",
                            {"foil_precut": 1, "charcoal_coco": 4, "hose_tip": 1}),
        "takeout": MenuItem("takeout", "Takeout order",
                            {"container_3c": 1, "container_lid": 1, "bag_paper": 1, "cutlery_kit": 1}),
    }


def sample_consumables():
    """Your stockroom. on_hand chosen so a few items are running hot for the demo."""
    return {c.id: c for c in [
        Consumable("cup_clear",     "16oz clear cups",          "bar",     on_hand=600,  unit_cost=0.07, pack_size=1000, lead_time_days=7),
        Consumable("straw",         "Paper straws",             "bar",     on_hand=2000, unit_cost=0.01, pack_size=5000, lead_time_days=7),
        Consumable("napkin",        "Cocktail napkins",         "bar",     on_hand=3000, unit_cost=0.005, pack_size=5000, lead_time_days=7),
        Consumable("foil_precut",   "Pre-cut hookah foil",      "hookah",  on_hand=200,  unit_cost=0.10, pack_size=500,  lead_time_days=14),
        Consumable("charcoal_coco", "Coconut charcoal cube",    "hookah",  on_hand=300,  unit_cost=0.06, pack_size=1000, lead_time_days=14),
        Consumable("hose_tip",      "Disposable hose tips",     "hookah",  on_hand=80,   unit_cost=0.03, pack_size=1000, lead_time_days=14),
        Consumable("container_3c",  "3-compartment container",  "takeout", on_hand=40,   unit_cost=0.23, pack_size=200,  lead_time_days=10),
        Consumable("container_lid", "Container lids",           "takeout", on_hand=300,  unit_cost=0.08, pack_size=500,  lead_time_days=10),
        Consumable("bag_paper",     "Paper takeout bags",       "takeout", on_hand=200,  unit_cost=0.05, pack_size=500,  lead_time_days=10),
        Consumable("cutlery_kit",   "Cutlery kits",             "takeout", on_hand=120,  unit_cost=0.12, pack_size=250,  lead_time_days=10),
    ]}


def sample_sales():
    """A month's POS counts (the numbers from your example)."""
    return {"drink": 500, "hookah": 120, "takeout": 85}
