#!/usr/bin/env python3
"""
importer.py — paste a list, get a catalog. You've been pasting Alibaba / Amazon
listings all along; this turns that straight into products. Each listing is parsed by
AI Ears (name, category, per-unit cost, sell) and written into the catalog with a
generated SKU. Then `describe` writes the copy and `publish` lists them.

  from ebe.store import Store
  from ebe.importer import import_listings, split_listings
  import_listings(Store("ebe.db"), split_listings(pasted_text))

Needs ANTHROPIC_API_KEY + the anthropic SDK (the same key `check` validates).
"""
from __future__ import annotations

import re


def split_listings(text):
    """Break pasted text into individual listings. Blank-line-separated blocks if present,
    otherwise one listing per line."""
    text = (text or "").strip()
    if not text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) > 1:
        return blocks
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def slug_sku(name, used, maxlen=28):
    """A clean, unique SKU from a product name (UPPER-DASHED), deduped against `used`."""
    base = re.sub(r"[^A-Za-z0-9]+", "-", (name or "").upper()).strip("-")
    base = base[:maxlen].strip("-") or "ITEM"
    sku, n = base, 2
    while sku in used:
        sku = "%s-%d" % (base[:maxlen - 3].strip("-"), n)
        n += 1
    return sku


def import_listings(store, listings, normalize_fn=None) -> dict:
    """Parse each listing → create a catalog product. Returns {created, failed}.
    Pass normalize_fn to test without the network (default uses AI Ears)."""
    fn = normalize_fn
    if fn is None:
        from .ai.ears import normalize
        fn = normalize
    used = {p["sku"] for p in store.products()}
    created, failed = [], []
    for raw in listings:
        try:
            d = fn(raw) or {}
            name = (d.get("name") or "").strip() or raw[:40]
            sku = (d.get("sku") or "").strip() or slug_sku(name, used)
            used.add(sku)
            row = {"sku": sku, "name": name[:80],
                   "category": d.get("category") or None,
                   "cost": float(d.get("cost") or 0),
                   "sell": float(d.get("sell") or 0)}
            store.upsert_products([row])
            created.append((sku, name))
        except Exception as e:
            failed.append((str(raw)[:40], str(e)))
    return {"created": created, "failed": failed}
