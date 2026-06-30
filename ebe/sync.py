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


def _stock_map(client):
    """{sku: units} from any channel — generic .stock() preferred, Amazon FBA as fallback."""
    if hasattr(client, "stock"):
        return client.stock()
    from .adapters.amazon_spapi import inventory_to_stock
    return inventory_to_stock(client.fba_inventory())


def _price_rows(client, skus):
    """[{sku, price}] from any channel — generic .prices() preferred, Amazon pricing as fallback."""
    if hasattr(client, "prices"):
        return client.prices(skus)
    rows = []
    for row in client.my_price(skus):
        sku, amount = _price_of(row)
        rows.append({"sku": sku, "price": amount})
    return rows


def sync_stock(store: Store, client, prices=False) -> dict:
    """Update on_hand (and optionally sell price) for SKUs the channel reports.

    `client` is any channel exposing stock() -> {sku: units} (Shopify, …) or the
    Amazon SpApiClient (fba_inventory). Returns a summary dict. Unknown SKUs are
    reported, never created.
    """
    stock = _stock_map(client)
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
            for row in _price_rows(client, [s for s, _ in updated]):
                sku, amount = row.get("sku"), row.get("price")
                if sku in known and amount:
                    p = store.product(sku)
                    if p:
                        store.upsert_products([{**p, "sell": amount}])
                        priced.append((sku, amount))
        except Exception:
            pass        # pricing is a bonus; never let it break a stock sync

    return {"updated": updated, "unknown": unknown, "priced": priced}


def channel_client(name, region="na", marketplace="us"):
    """Build a sync client for a named channel."""
    from .adapters.base import AdapterError
    if name == "amazon":
        from .adapters.amazon_spapi import SpApiClient
        return SpApiClient(region=region, marketplace=marketplace)
    if name == "shopify":
        from .adapters.shopify import ShopifyClient
        return ShopifyClient()
    if name == "ebay":
        from .adapters.ebay import EbayClient
        return EbayClient()
    raise AdapterError("unknown sync channel %r" % name)


def configured_channels():
    """Stock channels whose keys are present in .env (so sync --all skips the rest)."""
    from .adapters import config
    out = []
    for name in ("amazon", "shopify", "ebay"):
        keys = config.NEEDS.get(name, [])
        if keys and not config.require(keys):
            out.append(name)
    return out


def sync_all(store, prices=False, region="na", marketplace="us"):
    """Pull stock from every configured channel. Returns {channel: result-or-error}."""
    results = {}
    for name in configured_channels():
        try:
            results[name] = sync_stock(store, channel_client(name, region, marketplace), prices=prices)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results


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
