#!/usr/bin/env python3
"""
ears.py — the AI EARS organ (👂). Truth enters here, and it's usually messy.

Supplier listings are free-text noise — "Disposable Hookah Mouth Tips 1000pcs/box $30
MOQ 10 boxes, OEM available!!". AI Ears (Haiku, cheap) turns one such blurb into clean,
structured fields — name, category, per-UNIT cost, pack size, MOQ — that the sourcing /
discover branches can actually score. Garbage in, structure out.

The Ears only EXTRACT what's stated; they don't decide anything. The Brain/Heart still gate.
"""
from __future__ import annotations

from ..catalog.product import Product
from .client import ask_json, MODEL_FAST

_CATEGORIES = ("home", "kitchen", "hookah", "bar", "takeout", "apparel", "electronics",
               "beauty", "health", "pet", "fitness", "office", "other")

SYSTEM = (
    "You are the EARS organ of a sourcing engine. Turn ONE messy supplier listing into clean "
    "structured fields. Extract: name (short), category (one of: %s), cost (the buyer's per-UNIT "
    "cost in USD — if a case price is given, divide by the pack size), pack_size (units per case, "
    "default 1), sell (typical retail per unit if stated, else 0), moq (minimum order quantity, "
    "0 if unknown), notes (one short line). Only extract what's actually stated; use 0 or the "
    "default when unknown. Do not invent prices." % ", ".join(_CATEGORIES)
)

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "category": {"type": "string", "enum": list(_CATEGORIES)},
        "cost": {"type": "number"},
        "pack_size": {"type": "integer"},
        "sell": {"type": "number"},
        "moq": {"type": "integer"},
        "notes": {"type": "string"},
    },
    "required": ["name", "category", "cost", "pack_size", "sell", "moq", "notes"],
    "additionalProperties": False,
}


def normalize(raw):
    """One messy supplier listing (str) -> clean structured dict."""
    return ask_json(SYSTEM, "Listing:\n" + str(raw), SCHEMA, model=MODEL_FAST)


def to_product(d, i=1):
    """A normalized dict -> a Product the sourcing/discover branches read."""
    return Product(
        id="S%d" % i,
        name=(d.get("name") or "?")[:60],
        category=d.get("category") or "other",
        cost=float(d.get("cost") or 0),
        sell=float(d.get("sell") or 0),
        competition=0.5,
    )


def normalize_listings(listings, normalize_fn=None):
    """Many messy listings -> list[Product]. Pass normalize_fn to test without the network."""
    fn = normalize_fn or normalize
    return [to_product(fn(raw), i + 1) for i, raw in enumerate(listings)]
