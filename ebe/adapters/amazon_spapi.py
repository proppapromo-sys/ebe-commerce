#!/usr/bin/env python3
"""
amazon_spapi.py — LIVE Amazon Selling-Partner API (your real listings, stock, prices).

Auth note: since late 2023 SP-API needs ONLY a Login-with-Amazon (LWA) access token —
the old AWS SigV4 signing is gone. So this is just: trade your refresh token for an
access token, then send it as `x-amz-access-token`. No AWS SDK, no boto3.

You get the three secrets below once your SP-API app is approved (see SETUP.md):
  SPAPI_REFRESH_TOKEN · SPAPI_CLIENT_ID · SPAPI_CLIENT_SECRET

NOTE: Amazon does not know YOUR unit cost — merge it from your own `sku,cost` sheet to
turn live stock/price into full profit-after-fees decisions.
"""
from __future__ import annotations

from . import config
from .base import request_json, AdapterError

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

ENDPOINTS = {
    "na": "https://sellingpartnerapi-na.amazon.com",
    "eu": "https://sellingpartnerapi-eu.amazon.com",
    "fe": "https://sellingpartnerapi-fe.amazon.com",
}
MARKETPLACES = {
    "us": "ATVPDKIKX0DER", "ca": "A2EUQ1WTGCTBG2", "mx": "A1AM78C64UM0Y8",
    "uk": "A1F83G8C2ARO7P", "de": "A1PA6795UKMFR9", "fr": "A13V1IB3VIYZZH",
    "it": "APJ6JRA9NG5V4", "es": "A1RKKUPIHCS9HS", "jp": "A1VC38T7YXB528",
}


class SpApiClient:
    def __init__(self, region="na", marketplace="us", refresh_token=None,
                 client_id=None, client_secret=None):
        self.endpoint = ENDPOINTS.get(region, ENDPOINTS["na"])
        self.marketplace_id = MARKETPLACES.get(marketplace, MARKETPLACES["us"])
        self.refresh_token = refresh_token or config.get("SPAPI_REFRESH_TOKEN")
        self.client_id = client_id or config.get("SPAPI_CLIENT_ID")
        self.client_secret = client_secret or config.get("SPAPI_CLIENT_SECRET")
        if not all((self.refresh_token, self.client_id, self.client_secret)):
            raise AdapterError("SP-API creds missing (SPAPI_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET)")
        self._access_token = None

    def _token(self):
        if self._access_token:
            return self._access_token
        data = request_json("POST", LWA_TOKEN_URL, form={
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })
        self._access_token = data["access_token"]
        return self._access_token

    def _get(self, path, params=None):
        return request_json("GET", self.endpoint + path,
                            headers={"x-amz-access-token": self._token()}, params=params)

    def check(self):
        """Confirms the refresh token exchanges for an access token."""
        return bool(self._token())

    def fba_inventory(self):
        """FBA stock per SKU (raw inventorySummaries)."""
        data = self._get("/fba/inventory/v1/summaries", params={
            "granularityType": "Marketplace", "granularityId": self.marketplace_id,
            "marketplaceIds": self.marketplace_id, "details": "true",
        })
        return (data.get("payload") or {}).get("inventorySummaries", []) or []

    def my_price(self, skus):
        """Your current listing prices for a batch of SKUs (Product Pricing API)."""
        if not skus:
            return []
        data = self._get("/products/pricing/v0/price", params={
            "MarketplaceId": self.marketplace_id, "Skus": ",".join(skus), "ItemType": "Sku",
        })
        return data.get("payload", []) or []


# ── mapping (pure; verified against live shapes on first real call) ──────────
def inventory_to_stock(summaries):
    """inventorySummaries -> {sku: total_units}."""
    out = {}
    for s in summaries:
        sku = s.get("sellerSku") or s.get("asin")
        if sku is not None:
            out[sku] = int(s.get("totalQuantity") or 0)
    return out
