#!/usr/bin/env python3
"""
bundles.py — KITS THAT LIFT THE CART. A bundle is one sellable SKU made of component
SKUs: cost = sum of the parts, price is what you charge, and selling one draws down each
component's stock. Bundles convert better and carry fatter margins than singles — the
Hookah Starter Kit (holder + charcoal + tips) is worth more than any of its pieces alone.

  from ebe.store import Store
  from ebe.bundles import load_bundle_rows, margins
"""
from __future__ import annotations

import csv


def load_bundle_rows(path):
    """Read a bundles CSV (bundle_sku,name,price,component_sku,qty — repeat rows per kit).
    Returns {bundle_sku: {"name","price","components":[(sku,qty)]}}."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            b = (row.get("bundle_sku") or "").strip()
            comp = (row.get("component_sku") or "").strip()
            if not b or not comp:
                continue
            entry = out.setdefault(b, {"name": (row.get("name") or b).strip(),
                                       "price": float(row.get("price") or 0), "components": []})
            entry["components"].append((comp, int(float(row.get("qty") or 1))))
    return out


def load_into_store(store, path) -> int:
    """Define every bundle from the CSV in the store. Returns how many."""
    rows = load_bundle_rows(path)
    for sku, b in rows.items():
        store.define_bundle(sku, b["name"], b["price"], b["components"])
    return len(rows)


def margins(store, sku, fee):
    """Cost / net / margin / roi for a bundle on a given fee model."""
    b = store.bundle(sku)
    if not b:
        return None
    cost, price = b["cost"], b["price"]
    return {"sku": sku, "name": b["name"], "price": price, "cost": cost,
            "net_unit": round(fee.net_unit(price, cost), 2),
            "margin": fee.margin(price, cost), "roi": fee.roi(price, cost),
            "components": b["components"]}


def as_item(store, sku, monthly_sales=0, competition=0.4, category="hookah"):
    """Shape a bundle like a product item so channels.compare / edges can score it."""
    b = store.bundle(sku)
    if not b:
        return None
    return {"id": sku, "name": b["name"], "category": category,
            "cost": b["cost"], "sell": b["price"],
            "monthly_sales": monthly_sales, "competition": competition}
