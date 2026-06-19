#!/usr/bin/env python3
"""
shopify.py — LIVE Shopify Admin API (your own-brand DTC store: stock + prices).

Auth is a single Admin API access token (create a custom app in your Shopify admin →
Settings → Apps and sales channels → Develop apps). No OAuth dance needed for a
private/custom app on your own store.

  SHOPIFY_STORE   your store handle (the part before .myshopify.com)
  SHOPIFY_TOKEN   Admin API access token (shpat_...)

Matching is by variant SKU — set the same SKU on each Shopify variant as in your
catalog, and `python -m ebe sync --channel shopify` updates on-hand + price.
"""
from __future__ import annotations

from . import config
from .base import request_json, AdapterError

API_VERSION = "2024-01"


class ShopifyClient:
    def __init__(self, store=None, token=None, version=API_VERSION):
        self.store = store or config.get("SHOPIFY_STORE")
        self.token = token or config.get("SHOPIFY_TOKEN")
        if not all((self.store, self.token)):
            raise AdapterError("Shopify creds missing (SHOPIFY_STORE/SHOPIFY_TOKEN)")
        self.base = "https://%s.myshopify.com/admin/api/%s" % (self.store, version)

    def _get(self, path, params=None):
        return request_json("GET", self.base + path,
                            headers={"X-Shopify-Access-Token": self.token}, params=params)

    def check(self):
        """Confirms the token reaches your shop."""
        return bool(self._get("/shop.json").get("shop"))

    def variants(self):
        """All variants across products (one page of up to 250 — enough for most small stores)."""
        out = []
        data = self._get("/products.json", params={"limit": 250})
        for p in data.get("products", []) or []:
            out.extend(p.get("variants", []) or [])
        return out

    def stock(self):
        """{sku: on_hand} — the generic channel interface the sync layer expects."""
        return variants_to_stock(self.variants())

    def prices(self, skus=None):
        """[{sku, price}] for the given SKUs (or all)."""
        rows = []
        for v in self.variants():
            sku = v.get("sku")
            if sku and (skus is None or sku in skus):
                try:
                    rows.append({"sku": sku, "price": float(v.get("price") or 0)})
                except (TypeError, ValueError):
                    pass
        return rows


# ── pure mapping (verified against live shapes on first real call) ───────────
def variants_to_stock(variants):
    """Shopify variants -> {sku: inventory_quantity}."""
    out = {}
    for v in variants:
        sku = v.get("sku")
        if sku:
            try:
                out[sku] = int(v.get("inventory_quantity") or 0)
            except (TypeError, ValueError):
                out[sku] = 0
    return out
