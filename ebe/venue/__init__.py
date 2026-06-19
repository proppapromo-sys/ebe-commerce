"""
Venue supply tracking — point the genome at YOUR venue instead of Amazon.

Phase 1: POS counts (drinks / hookahs / takeout) → bill-of-materials → supplies consumed
→ the same restock brain the Amazon inventory branch runs → "you'll run out in N days, reorder?"

This is the differentiated business: you already know what a venue burns, breaks, wastes and
restocks. This turns that operating knowledge into software + supply + auto-reorder.
"""
from .bom import Consumable, MenuItem, explode_usage
from . import engine, sample

__all__ = ["Consumable", "MenuItem", "explode_usage", "engine", "sample"]
