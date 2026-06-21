#!/usr/bin/env python3
"""
shopify.py — LIVE Shopify Admin API (your own-brand DTC store: stock + prices).

Auth (2026+): Shopify deprecated the old "reveal token" custom apps. A Dev Dashboard
app gives a Client ID + Client Secret, which EBE exchanges for a 24h Admin API access
token using the CLIENT CREDENTIALS GRANT — server-to-server, no browser, no redirect.
This works because the app and store are in the same Shopify organization (your own).

  SHOPIFY_STORE          your store handle (the part before .myshopify.com)
  SHOPIFY_CLIENT_ID      Dev Dashboard app → Settings → Client ID      (preferred)
  SHOPIFY_CLIENT_SECRET  Dev Dashboard app → Settings → Client secret  (preferred)
  SHOPIFY_TOKEN          a static Admin API token, if you still have a legacy one

If CLIENT_ID + CLIENT_SECRET are set, EBE mints a fresh token every run (so the 24h
expiry never bites). A static SHOPIFY_TOKEN is used only as a fallback.

Matching is by variant SKU — set the same SKU on each Shopify variant as in your
catalog, and `python -m ebe sync --channel shopify` updates on-hand + price.
"""
from __future__ import annotations

from . import config
from .base import request_json, AdapterError

API_VERSION = "2024-01"


def mint_access_token(store, client_id, client_secret):
    """Client credentials grant → (token, expires_in). Token is valid ~24h.
    Only works for a first-party app installed on a store in your own organization."""
    data = request_json(
        "POST", "https://%s.myshopify.com/admin/oauth/access_token" % store,
        json_body={"client_id": client_id, "client_secret": client_secret,
                   "grant_type": "client_credentials"})
    token = data.get("access_token")
    if not token:
        raise AdapterError("Shopify client-credentials returned no access_token: %s" % data)
    return token, data.get("expires_in")


class ShopifyClient:
    def __init__(self, store=None, token=None, version=API_VERSION):
        self.store = store or config.get("SHOPIFY_STORE")
        client_id = config.get("SHOPIFY_CLIENT_ID")
        client_secret = config.get("SHOPIFY_CLIENT_SECRET")
        self.token = token or None
        # Preferred 2026 path: mint a fresh token from Client ID + Secret.
        if not self.token and self.store and client_id and client_secret:
            self.token, _ = mint_access_token(self.store, client_id, client_secret)
        # Fallback: a legacy static Admin API token, if that's all that's set.
        if not self.token:
            self.token = config.get("SHOPIFY_TOKEN")
        if not all((self.store, self.token)):
            raise AdapterError(
                "Shopify creds missing — set SHOPIFY_STORE + SHOPIFY_CLIENT_ID + "
                "SHOPIFY_CLIENT_SECRET in .env")
        self.base = "https://%s.myshopify.com/admin/api/%s" % (self.store, version)

    def _get(self, path, params=None):
        return request_json("GET", self.base + path,
                            headers={"X-Shopify-Access-Token": self.token}, params=params)

    def _post(self, path, body):
        return request_json("POST", self.base + path,
                            headers={"X-Shopify-Access-Token": self.token,
                                     "Content-Type": "application/json"},
                            json_body=body)

    def check(self):
        """Confirms the token reaches your shop."""
        return bool(self._get("/shop.json").get("shop"))

    def locations(self):
        return self._get("/locations.json").get("locations", []) or []

    def primary_location_id(self):
        """The first active location id — where inventory levels are set."""
        for loc in self.locations():
            if loc.get("active", True):
                return loc.get("id")
        return None

    def set_inventory_level(self, inventory_item_id, location_id, available):
        return self._post("/inventory_levels/set.json",
                          {"location_id": location_id,
                           "inventory_item_id": inventory_item_id,
                           "available": int(available)})

    def create_product(self, sku, title, price, body_html="", qty=None, status="active"):
        """Create a product+variant on Shopify (needs write_products scope).
        qty=None lists it untracked (always available); an int tracks + sets stock
        (needs write_inventory). Returns the created product dict."""
        variant = {"sku": sku, "price": "%.2f" % float(price or 0)}
        if qty is not None:
            variant["inventory_management"] = "shopify"
        body = {"product": {"title": title, "body_html": body_html or "",
                            "status": status, "variants": [variant]}}
        prod = (self._post("/products.json", body) or {}).get("product") or {}
        if qty is not None:
            try:
                inv_item = (prod.get("variants") or [{}])[0].get("inventory_item_id")
                loc = self.primary_location_id()
                if inv_item and loc:
                    self.set_inventory_level(inv_item, loc, int(qty))
            except Exception:
                pass        # product created; stock can be set later in Shopify
        return prod


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
