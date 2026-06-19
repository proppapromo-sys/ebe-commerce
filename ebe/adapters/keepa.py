#!/usr/bin/env python3
"""
keepa.py — LIVE sourcing data (usable today: a Keepa key is instant).

Keepa knows a product's live buy-box PRICE and how many units it SELLS per month — the
two things your sourcing brain can't guess. It does NOT know YOUR cost, so the workflow
is: you supply an `asin,cost` list (your supplier quotes); Keepa fills in sell price +
real demand + category; the sourcing branch then scores profit-after-fees on real numbers.

  asin,cost                      KEEPA_API_KEY=...  (.env)
  B0XXXXXXX1,5.20      ──▶ Keepa ──▶  sell, monthly_sales, category  ──▶  Product
  B0XXXXXXX2,11.00

Docs: https://keepa.com/#!discuss/t/product-object   https://keepa.com/#!api
"""
from __future__ import annotations

import csv
import json

from . import config
from .base import request_json, AdapterError
from ..catalog.product import Product

KEEPA_DOMAINS = {"us": 1, "uk": 2, "de": 3, "fr": 4, "jp": 5, "ca": 6, "it": 8, "es": 9, "in": 10, "mx": 11}

# A few common Amazon-US root category browse-node IDs Keepa's Product Finder accepts.
KEEPA_CATEGORIES = {
    "home": 1055398,        # Home & Kitchen
    "kitchen": 1055398,
    "health": 3760901,      # Health & Household
    "beauty": 3760911,      # Beauty & Personal Care
    "sports": 3375251,      # Sports & Outdoors
    "toys": 165793011,      # Toys & Games
    "pet": 2619533011,      # Pet Supplies
    "office": 1064954,      # Office Products
    "garden": 2972638011,   # Patio, Lawn & Garden
    "baby": 165796011,      # Baby
    "electronics": 172282,  # Electronics
    "apparel": 7141123011,  # Clothing, Shoes & Jewelry
}


class KeepaClient:
    def __init__(self, key=None, domain="us"):
        self.key = key or config.get("KEEPA_API_KEY")
        if not self.key:
            raise AdapterError("KEEPA_API_KEY not set (put it in .env)")
        self.domain = KEEPA_DOMAINS.get(domain, 1)

    def check(self):
        """Lightweight ping — returns remaining token balance."""
        data = request_json("GET", "https://api.keepa.com/token", params={"key": self.key})
        return data.get("tokensLeft", data)

    def fetch(self, asins):
        """Fetch raw Keepa product objects for up to ~100 ASINs per call."""
        if not asins:
            return []
        data = request_json("GET", "https://api.keepa.com/product", params={
            "key": self.key, "domain": self.domain,
            "asin": ",".join(asins), "stats": 1, "buybox": 1,
        })
        return data.get("products", []) or []

    def product_finder(self, selection):
        """Keepa Product Finder — returns a list of ASINs matching a selection dict.
        Docs: https://keepa.com/#!discuss/t/product-finder/5473"""
        data = request_json("GET", "https://api.keepa.com/query", params={
            "key": self.key, "domain": self.domain, "selection": json.dumps(selection),
        })
        return data.get("asinList", []) or []


# ── mapping (pure functions — unit-tested without the network) ───────────────
def _cents(v):
    """Keepa prices are integer cents; -1 means 'no data'."""
    return None if v is None or v < 0 else round(v / 100.0, 2)


def keepa_sell_price(kp):
    """Best available current sell price, in dollars."""
    stats = kp.get("stats") or {}
    for v in (stats.get("buyBoxPrice"), (stats.get("current") or [None])[0]):
        p = _cents(v)
        if p:
            return p
    return 0.0


def keepa_monthly_sales(kp):
    """Real units/month Keepa observed (0 if Keepa has no estimate)."""
    return float(kp.get("monthlySold") or 0)


def keepa_competition(kp):
    """Rough 0..1 saturation from the live offer count (more sellers -> more crowded)."""
    stats = kp.get("stats") or {}
    offers = stats.get("offerCountFBA") or stats.get("totalOfferCount") or 0
    return max(0.0, min(1.0, offers / 20.0))


def keepa_category(kp):
    tree = kp.get("categoryTree") or []
    if tree:
        return (tree[-1].get("name") or "?").lower()
    return (kp.get("productGroup") or "?").lower()


def to_product(kp, cost, fulfilment=4.0):
    """One live Keepa object + your unit cost -> a sourcing candidate."""
    return Product(
        id=kp.get("asin", "?"),
        name=(kp.get("title") or kp.get("asin") or "?")[:60],
        category=keepa_category(kp),
        cost=float(cost),
        sell=keepa_sell_price(kp),
        fulfilment=fulfilment,
        monthly_sales=keepa_monthly_sales(kp),
        competition=keepa_competition(kp),
    )


def load_asin_costs(path):
    """Read an `asin,cost[,fulfilment]` CSV -> [(asin, cost, fulfilment), ...]."""
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            asin = (row.get("asin") or "").strip()
            if not asin:
                continue
            rows.append((asin, float(row.get("cost") or 0),
                         float(row.get("fulfilment") or 4.0)))
    return rows


def sourcing_candidates(asin_cost_path, client=None, domain="us"):
    """Top-level: asin,cost CSV -> live Keepa enrichment -> list[Product]."""
    client = client or KeepaClient(domain=domain)
    rows = load_asin_costs(asin_cost_path)
    costs = {a: (c, f) for a, c, f in rows}
    by_asin = {kp.get("asin"): kp for kp in client.fetch([a for a, _, _ in rows])}
    out = []
    for asin, (cost, ful) in costs.items():
        kp = by_asin.get(asin)
        if kp:
            out.append(to_product(kp, cost, ful))
    return out


# ── DISCOVERY — let Keepa hand you candidate products (not the other way round) ─
def build_selection(category=None, min_monthly=100, min_price=15.0, max_price=60.0,
                    max_sellers=None, limit=30):
    """Translate friendly filters into a Keepa Product-Finder selection."""
    sel = {
        "perPage": int(limit),
        "page": 0,
        "monthlySold_gte": int(min_monthly),
        "current_BUY_BOX_SHIPPING_gte": int(round(min_price * 100)),
        "current_BUY_BOX_SHIPPING_lte": int(round(max_price * 100)),
        "sort": [["monthlySold", "desc"]],
    }
    if category and category.lower() in KEEPA_CATEGORIES:
        sel["rootCategory"] = [KEEPA_CATEGORIES[category.lower()]]
    if max_sellers is not None:
        sel["current_COUNT_NEW_lte"] = int(max_sellers)
    return sel


def discover_candidates(category=None, min_monthly=100, min_price=15.0, max_price=60.0,
                        max_sellers=None, limit=30, cost_ratio=0.35, client=None, domain="us"):
    """Keepa Product Finder -> enriched candidates with an ASSUMED landed cost.

    Discovery finds high-demand / low-competition products for you; it can't know your
    real cost, so cost is set to `cost_ratio` × sell price (a labelled placeholder you
    replace with real supplier quotes for the shortlist that survives)."""
    client = client or KeepaClient(domain=domain)
    asins = client.product_finder(build_selection(
        category, min_monthly, min_price, max_price, max_sellers, limit))
    out = []
    for kp in client.fetch(asins[:limit]):
        sell = keepa_sell_price(kp)
        if sell <= 0:
            continue
        out.append(to_product(kp, cost=round(sell * cost_ratio, 2)))
    return out
