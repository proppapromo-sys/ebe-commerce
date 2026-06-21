#!/usr/bin/env python3
"""
config.py — credentials, loaded from a local .env (never commit it). Pure stdlib:
a tiny KEY=VALUE parser, so there's no python-dotenv dependency. Real keys live in
.env on your machine / server; .env.example documents what's needed.
"""
from __future__ import annotations

import os

_LOADED = False


def load_env(path=".env"):
    """Read KEY=VALUE lines into the environment (existing env vars win)."""
    global _LOADED
    if not os.path.exists(path):
        _LOADED = True
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
    _LOADED = True


def get(key, default=None):
    if not _LOADED:
        load_env()
    return os.environ.get(key, default)


def require(keys):
    """Return the subset of keys that are missing/empty (for the doctor command)."""
    return [k for k in keys if not get(k)]


def set_env(key, value, path=".env"):
    """Upsert KEY=value in .env (create the file if needed). Also updates the live process."""
    import os
    lines, found = [], False
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith(key + "="):
                    lines.append("%s=%s\n" % (key, value)); found = True
                else:
                    lines.append(line)
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append("%s=%s\n" % (key, value))
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    os.environ[key] = value


# Which env vars each integration needs:
# The full integration catalogue — one source of truth for the doctor (`check`),
# the connections map (`connections`), and docs/INTEGRATIONS.md.
# status: "live" = adapter built & wired · "planned" = sign up now, adapter ready to build.
INTEGRATIONS = {
    "ai":          {"label": "Anthropic (AI brain)", "keys": ["ANTHROPIC_API_KEY"],
                    "signup": "https://console.anthropic.com", "status": "live",
                    "role": "The brain — demand calls, AI eyes/ears, written daily brief"},
    "keepa":       {"label": "Keepa (market data)", "keys": ["KEEPA_API_KEY"],
                    "signup": "https://keepa.com/#!api", "status": "live",
                    "role": "Live price/sales/rank, Product Finder, buy-the-dip arbitrage"},
    "amazon":      {"label": "Amazon Selling Partner API", "keys": ["SPAPI_REFRESH_TOKEN", "SPAPI_CLIENT_ID", "SPAPI_CLIENT_SECRET"],
                    "signup": "https://sellercentral.amazon.com", "status": "live",
                    "role": "Your real listings, stock & prices → the database (sync)"},
    "amazon-ads":  {"label": "Amazon Ads API", "keys": ["ADS_REFRESH_TOKEN", "ADS_CLIENT_ID", "ADS_CLIENT_SECRET", "ADS_PROFILE_ID"],
                    "signup": "https://advertising.amazon.com/API/docs", "status": "live",
                    "role": "Campaign spend/sales → scale winners, cut bleeders"},
    "shopify":     {"label": "Shopify (your DTC store)",
                    "keys": ["SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"],
                    "signup": "https://www.shopify.com", "status": "live",
                    "role": "Own-brand storefront — stock & price sync into the database"},
    "square":      {"label": "Square (venue POS)", "keys": ["SQUARE_TOKEN", "SQUARE_LOCATION_ID"],
                    "signup": "https://squareup.com/pos", "status": "live",
                    "role": "Pull real venue sales → consumption → auto-reorder supplies"},
    "ebay":        {"label": "eBay", "keys": ["EBAY_TOKEN"],
                    "signup": "https://developer.ebay.com", "status": "planned",
                    "role": "Second resale channel for merch & overstock"},
    "etsy":        {"label": "Etsy", "keys": ["ETSY_API_KEY", "ETSY_TOKEN"],
                    "signup": "https://www.etsy.com/developers", "status": "planned",
                    "role": "Handmade/print apparel channel"},
    "walmart":     {"label": "Walmart Marketplace", "keys": ["WALMART_CLIENT_ID", "WALMART_CLIENT_SECRET"],
                    "signup": "https://marketplace.walmart.com", "status": "planned",
                    "role": "High-volume third channel once Amazon is humming"},
    "tiktok":      {"label": "TikTok Shop", "keys": ["TIKTOK_APP_KEY", "TIKTOK_APP_SECRET"],
                    "signup": "https://seller-us.tiktok.com", "status": "planned",
                    "role": "Social-commerce for the merch/brand play"},
    "printful":    {"label": "Printful (print-on-demand)", "keys": ["PRINTFUL_TOKEN"],
                    "signup": "https://www.printful.com", "status": "planned",
                    "role": "Auto-fulfil own-brand apparel — no inventory risk"},
    "stripe":      {"label": "Stripe (payments)", "keys": ["STRIPE_SECRET_KEY"],
                    "signup": "https://stripe.com", "status": "live",
                    "role": "Real revenue + available balance → the brief & cash forecast"},
}

# Which env vars each LIVE integration needs (derived; the doctor validates these):
NEEDS = {name: meta["keys"] for name, meta in INTEGRATIONS.items() if meta["status"] == "live"}
