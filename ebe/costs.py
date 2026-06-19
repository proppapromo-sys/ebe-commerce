#!/usr/bin/env python3
"""
costs.py — your real numbers, overlaid. Catalog/stock/price come from one place (a products
export, or live Amazon SP-API); your supplier COSTS change independently, so keep them in
their own `sku,cost` sheet and merge them in. Same for live stock.

  apply_costs(products, load_cost_sheet("my_costs.csv"))   # real margins everywhere
  apply_stock(products, spapi.inventory_to_stock(...))     # real on-hand from SP-API
"""
from __future__ import annotations

import csv


def load_cost_sheet(path) -> dict:
    """`sku,cost[,fulfilment]` CSV -> {sku: {cost, fulfilment?}}."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sku = (row.get("sku") or row.get("id") or "").strip()
            if not sku:
                continue
            entry = {}
            if (row.get("cost") or "").strip():
                entry["cost"] = float(row["cost"])
            if (row.get("fulfilment") or "").strip():
                entry["fulfilment"] = float(row["fulfilment"])
            if entry:
                out[sku] = entry
    return out


def apply_costs(products, sheet):
    """Overlay cost (and fulfilment) onto matching Products by id. Mutates and returns them."""
    for p in products:
        e = sheet.get(p.id)
        if e:
            if "cost" in e:
                p.cost = e["cost"]
            if "fulfilment" in e:
                p.fulfilment = e["fulfilment"]
    return products


def apply_stock(products, stock_map):
    """Overlay live on-hand by sku (e.g. SP-API inventory_to_stock). Simple products match by id;
    apparel variants match 'id·size/color' or the bare variant sku."""
    for p in products:
        if not p.variants and p.id in stock_map:
            p.on_hand = int(stock_map[p.id])
        for v in p.variants:
            key = "%s·%s" % (p.id, v.sku)
            if key in stock_map:
                v.on_hand = int(stock_map[key])
            elif v.sku in stock_map:
                v.on_hand = int(stock_map[v.sku])
    return products
