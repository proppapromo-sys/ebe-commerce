#!/usr/bin/env python3
"""
csv_io.py — feed the engine YOUR real numbers. Export your catalog / inventory / ad
campaigns to CSV (from Seller Central, Shopify, or just a spreadsheet) and load them
straight in — no code edits, no sample data.

PRODUCTS CSV — one row per SKU. Apparel products repeat the product columns across
several rows, one per size/colour variant:

  id,name,category,cost,sell,fulfilment,competition,lead_time_days,elasticity,size,color,on_hand,monthly_sales
  P1,LED strip lights,home,5,22,4,0.4,18,1.8,,,900,800
  M1,Graphic tee,apparel,9,28,5,0.5,21,1.6,S,Black,15,40
  M1,Graphic tee,apparel,9,28,5,0.5,21,1.6,M,Black,60,120

Rows that share an `id` become one Product; any row with a size or colour makes it
apparel (with per-variant stock). Leave size/colour blank for simple products and put
the product's total stock + demand in on_hand / monthly_sales.

CAMPAIGNS CSV — one row per advertised SKU:

  id,name,category,sell,cost,spend,ad_sales,target_acos
  C-P1,LED strips,home,22,5,600,4200,0.25
"""
from __future__ import annotations

import csv

from .product import Product, Variant


def _f(row, key, default=0.0):
    """Parse a float cell, tolerating blanks/missing columns."""
    v = (row.get(key) or "").strip()
    return float(v) if v else float(default)


def _i(row, key, default=0):
    return int(round(_f(row, key, default)))


def _s(row, key, default=""):
    return (row.get(key) or "").strip() or default


def load_products(path) -> list:
    """Read a products CSV into a list of Product (grouping variant rows by id)."""
    by_id = {}
    order = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = _s(row, "id")
            if not pid:
                continue
            if pid not in by_id:
                by_id[pid] = Product(
                    id=pid, name=_s(row, "name", pid), category=_s(row, "category", "?"),
                    cost=_f(row, "cost"), sell=_f(row, "sell"),
                    fulfilment=_f(row, "fulfilment", 4.0),
                    competition=_f(row, "competition", 0.5),
                    on_hand=_i(row, "on_hand"), monthly_sales=_f(row, "monthly_sales"),
                    lead_time_days=_i(row, "lead_time_days", 21),
                    elasticity=_f(row, "elasticity", 1.5),
                )
                order.append(pid)
            size, color = _s(row, "size"), _s(row, "color")
            if size or color:                       # this row describes an apparel variant
                p = by_id[pid]
                p.variants.append(Variant(size=size or "OS", color=color or "-",
                                          on_hand=_i(row, "on_hand"),
                                          monthly_sales=_f(row, "monthly_sales")))
                p.on_hand = 0                        # stock now lives on the variants
                p.monthly_sales = 0.0
    return [by_id[pid] for pid in order]


def load_store_rows(path) -> list:
    """Read a products CSV into per-sellable-unit dicts for the database (Store).

    A simple product becomes one row keyed by its id; an apparel product becomes one
    row per size/colour variant, with a unique sku like 'M2·OS·Navy' so each variant
    carries its own stock and demand for the re-buy engine.
    """
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = _s(row, "id")
            if not pid:
                continue
            size, color = _s(row, "size"), _s(row, "color")
            base = {
                "name": _s(row, "name", pid), "category": _s(row, "category", "?"),
                "cost": _f(row, "cost"), "sell": _f(row, "sell"),
                "fulfilment": _f(row, "fulfilment", 4.0),
                "lead_time_days": _i(row, "lead_time_days", 21),
                "on_hand": _i(row, "on_hand"), "monthly_sales": _i(row, "monthly_sales"),
                "supplier": _s(row, "supplier"),
            }
            if size or color:
                tag = "·".join(x for x in (size, color) if x)
                base["sku"] = "%s·%s" % (pid, tag)
                base["name"] = "%s %s" % (base["name"], tag)
            else:
                base["sku"] = pid
            out.append(base)
    return out


def load_campaigns(path) -> list:
    """Read a campaigns CSV into the list[dict] the adspend branch consumes."""
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cid = _s(row, "id")
            if not cid:
                continue
            out.append({
                "id": cid, "name": _s(row, "name", cid), "category": _s(row, "category", "?"),
                "sell": _f(row, "sell"), "cost": _f(row, "cost"),
                "spend": _f(row, "spend"), "ad_sales": _f(row, "ad_sales"),
                "target_acos": _f(row, "target_acos", 0.30),
            })
    return out
