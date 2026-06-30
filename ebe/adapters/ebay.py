#!/usr/bin/env python3
"""
ebay.py — LIVE eBay Sell APIs (your listings: stock, and price via offers). A second
resale channel that plugs into the same sync loop as Shopify/Amazon via the generic
stock()/prices() interface.

Auth is OAuth2: EBE trades your refresh token for an access token (HTTP Basic with your
App's Client ID + Secret), then calls the Sell Inventory API. No SDK.

  EBAY_CLIENT_ID       your eBay app Client ID (App ID)
  EBAY_CLIENT_SECRET   your eBay app Client Secret (Cert ID)
  EBAY_REFRESH_TOKEN   a user OAuth refresh token (sell.inventory scope)

Matching is by SKU — your eBay inventory-item SKU must equal the sku in your catalog.
"""
from __future__ import annotations

import base64

from . import config
from .base import request_json, AdapterError

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
API = "https://api.ebay.com"
SCOPE = "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly"


class EbayClient:
    def __init__(self, client_id=None, client_secret=None, refresh_token=None):
        self.client_id = client_id or config.get("EBAY_CLIENT_ID")
        self.client_secret = client_secret or config.get("EBAY_CLIENT_SECRET")
        self.refresh_token = refresh_token or config.get("EBAY_REFRESH_TOKEN")
        if not all((self.client_id, self.client_secret, self.refresh_token)):
            raise AdapterError("eBay creds missing "
                               "(EBAY_CLIENT_ID/EBAY_CLIENT_SECRET/EBAY_REFRESH_TOKEN)")
        self._access = None

    def _token(self):
        if self._access:
            return self._access
        basic = base64.b64encode(("%s:%s" % (self.client_id, self.client_secret)).encode()).decode()
        data = request_json("POST", OAUTH_URL,
                            headers={"Authorization": "Basic %s" % basic},
                            form={"grant_type": "refresh_token",
                                  "refresh_token": self.refresh_token, "scope": SCOPE})
        self._access = data["access_token"]
        return self._access

    def _get(self, path, params=None):
        return request_json("GET", API + path,
                            headers={"Authorization": "Bearer %s" % self._token(),
                                     "Accept": "application/json"}, params=params)

    def check(self):
        """Confirms the refresh token exchanges for an access token."""
        return bool(self._token())

    def inventory_items(self, limit=200):
        """Your inventory items (SKU + ship-to availability)."""
        data = self._get("/sell/inventory/v1/inventory_item", params={"limit": limit})
        return data.get("inventoryItems", []) or []

    def offers_for(self, sku):
        """Offers (with price) for one SKU."""
        data = self._get("/sell/inventory/v1/offer", params={"sku": sku})
        return data.get("offers", []) or []

    # ── generic channel interface (sync layer expects these) ────────────────
    def stock(self):
        """{sku: on_hand}."""
        return inventory_to_stock(self.inventory_items())

    def prices(self, skus=None):
        """[{sku, price}] — pulled per-SKU from offers (best effort)."""
        rows = []
        for sku in (skus or []):
            try:
                for off in self.offers_for(sku):
                    amount = (((off.get("pricingSummary") or {}).get("price") or {}).get("value"))
                    if amount is not None:
                        rows.append({"sku": sku, "price": float(amount)})
                        break
            except Exception:
                pass        # price is a bonus; never break the stock sync
        return rows


# ── pure mapping (verified against live shapes on first real call) ───────────
def inventory_to_stock(items):
    """eBay inventoryItems -> {sku: quantity}."""
    out = {}
    for it in items:
        sku = it.get("sku")
        qty = (((it.get("availability") or {}).get("shipToLocationAvailability") or {}).get("quantity"))
        if sku is not None:
            try:
                out[sku] = int(qty or 0)
            except (TypeError, ValueError):
                out[sku] = 0
    return out
