#!/usr/bin/env python3
"""
bom.py — venue supply tracking, the core mechanic: a "bill of materials" per thing you SELL.

A venue doesn't sell cups — it sells drinks, hookahs, takeout orders. Each of those
quietly CONSUMES supplies. The BOM is the recipe: 1 hookah = 1 foil + 4 charcoal + 1 tip.
Feed in what you sold and the engine knows exactly what got used — the thing a venue
owner usually only finds out when they run out mid-rush.

  sold: 500 drinks · 120 hookahs · 85 takeout   ──BOM──▶   exact supplies consumed
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Consumable:
    """A supply you stock and reorder. pack_size = how many come in one case/box."""
    id: str
    name: str
    category: str            # "bar" | "hookah" | "takeout"
    on_hand: int
    unit_cost: float
    pack_size: int = 1       # you reorder in cases of this many
    lead_time_days: int = 10


@dataclass
class MenuItem:
    """Something you SELL, with the supplies one sale consumes."""
    id: str
    name: str
    bom: dict = field(default_factory=dict)   # {consumable_id: qty consumed per sale}


def explode_usage(sales, menu) -> dict:
    """sales {menu_id: count} × each item's BOM -> {consumable_id: total units used}."""
    usage = {}
    for mid, count in sales.items():
        item = menu.get(mid)
        if not item:
            continue
        for cid, per in item.bom.items():
            usage[cid] = usage.get(cid, 0.0) + per * count
    return usage
