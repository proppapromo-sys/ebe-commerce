#!/usr/bin/env python3
"""
sales.py — WHAT ACTUALLY SOLD. Pulls real orders from a channel and records each line
item as a sale, so EBE runs on truth: real revenue, real units, real demand feeding the
re-buy engine — not just stock decrements. Idempotent: every order is keyed, so syncing
twice never double-counts.

  Shopify orders  →  record_sale per SKU  →  ledger / brief / autobuy see real movement

  from ebe.store import Store
  from ebe.adapters.shopify import ShopifyClient
  from ebe.sales import pull_orders
  pull_orders(Store("ebe.db"), ShopifyClient(), days=30)
"""
from __future__ import annotations


def pull_orders(store, client, days=30, channel="shopify") -> dict:
    """Record sales from a channel's recent orders. Returns a summary.

    Matches line items by SKU (unknown SKUs are counted in revenue but not stock).
    Already-recorded orders are skipped — safe to run on a schedule.
    """
    seen = store.channel_orders_seen()
    known = {p["sku"] for p in store.products()}
    new_orders, units, revenue = 0, 0, 0.0
    by_sku, unknown = {}, set()
    for o in client.orders(days=days):
        key = "%s:%s" % (channel, o.get("id"))
        if not o.get("id") or key in seen:
            continue
        order_rev = 0.0
        for li in o.get("line_items", []) or []:
            sku = li.get("sku")
            qty = int(li.get("quantity") or 0)
            price = float(li.get("price") or 0)
            if qty <= 0:
                continue
            order_rev += qty * price
            if sku and sku in known:
                store.record_sale(sku, qty)
                by_sku[sku] = by_sku.get(sku, 0) + qty
                units += qty
            elif sku:
                unknown.add(sku)
        store.record_channel_order(key, order_rev)
        revenue += order_rev
        new_orders += 1
    return {"orders": new_orders, "units": units, "revenue": round(revenue, 2),
            "by_sku": by_sku, "unknown": sorted(unknown)}
