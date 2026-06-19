#!/usr/bin/env python3
"""
sync.py — pull LIVE Amazon stock (and prices) into the database, so the re-buy
engine runs on truth instead of numbers you typed. One call closes the loop:

    Amazon SP-API  →  on_hand / sell in the Store  →  autobuy raises real POs

Matching is by SKU string: your Seller-Central seller-SKU must equal the sku in the
database (load your catalog with those same SKUs). Unknown SKUs are reported, not
guessed at. Amazon never knows your unit COST — keep that in your catalog/cost sheet.
"""
from __future__ import annotations

from .store import Store


def sync_stock(store: Store, client, prices=False) -> dict:
    """Update on_hand (and optionally sell price) for SKUs Amazon reports.

    `client` is anything exposing fba_inventory() and (if prices) my_price(skus) —
    the real SpApiClient, or a stub in tests. Returns a summary dict.
    """
    from .adapters.amazon_spapi import inventory_to_stock

    stock = inventory_to_stock(client.fba_inventory())
    known = {p["sku"] for p in store.products()}
    updated, unknown = [], []
    for sku, units in stock.items():
        if sku in known:
            store.set_stock(sku, units)
            updated.append((sku, units))
        else:
            unknown.append(sku)

    priced = []
    if prices and updated:
        try:
            for row in client.my_price([s for s, _ in updated]):
                sku, amount = _price_of(row)
                if sku in known and amount:
                    p = store.product(sku)
                    if p:
                        store.upsert_products([{**p, "sell": amount}])
                        priced.append((sku, amount))
        except Exception:
            pass        # pricing is a bonus; never let it break a stock sync

    return {"updated": updated, "unknown": unknown, "priced": priced}


def _price_of(row):
    """Best-effort dig of (sku, amount) out of a Product-Pricing payload row."""
    sku = row.get("SellerSKU") or row.get("sellerSku") or row.get("ASIN")
    amount = None
    try:
        offers = (((row.get("Product") or {}).get("Offers")) or [])
        if offers:
            amount = float(offers[0]["BuyingPrice"]["ListingPrice"]["Amount"])
    except (KeyError, IndexError, TypeError, ValueError):
        amount = None
    return sku, amount
