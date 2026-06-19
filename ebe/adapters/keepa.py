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

    def fetch(self, asins, stats_days=90):
        """Fetch raw Keepa product objects for up to ~100 ASINs per call.
        stats_days asks Keepa for current/avg/min/max over that window (powers arbitrage)."""
        if not asins:
            return []
        data = request_json("GET", "https://api.keepa.com/product", params={
            "key": self.key, "domain": self.domain,
            "asin": ",".join(asins), "stats": int(stats_days), "buybox": 1,
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


# Keepa price-type indices: 18 = Buy Box, 1 = New (3rd-party), 0 = Amazon. We try in that order.
_PRICE_TYPES = (18, 1, 0)


def _price_of(v):
    """A Keepa stat cell is either a cents value or a [timestamp, cents] pair."""
    if isinstance(v, list) and v:
        v = v[-1]
    return _cents(v) if isinstance(v, (int, float)) else None


def _stat_arr(stats, key):
    arr = stats.get(key)
    if not isinstance(arr, list):
        return None
    for idx in _PRICE_TYPES:
        if len(arr) > idx:
            p = _price_of(arr[idx])
            if p:
                return p
    return None


def keepa_price_points(kp):
    """{current, avg, min, max} sell price in dollars over Keepa's stats window.
    Defensive across Keepa's flat-array (avg) vs [ts,price]-pair (min/max) shapes."""
    st = kp.get("stats") or {}
    pts = {
        "current": _stat_arr(st, "current") or _cents(st.get("buyBoxPrice")) or keepa_sell_price(kp),
        "avg": _stat_arr(st, "avg") or _stat_arr(st, "avg90") or _stat_arr(st, "avg30"),
        "min": _stat_arr(st, "min"),
        "max": _stat_arr(st, "max"),
    }
    return pts


_RANK_IDX = 3       # Keepa price-type index 3 = SALES rank


def _rank_of(v):
    if isinstance(v, list) and v:
        v = v[-1]
    return int(v) if isinstance(v, (int, float)) and v > 0 else None


def _stat_rank(stats, key):
    arr = stats.get(key)
    if isinstance(arr, list) and len(arr) > _RANK_IDX:
        return _rank_of(arr[_RANK_IDX])
    return None


def keepa_rank_points(kp):
    """{current_rank, avg_rank} sales rank over Keepa's stats window (lower = selling more)."""
    st = kp.get("stats") or {}
    return {
        "current_rank": _stat_rank(st, "current") or kp.get("salesRank"),
        "avg_rank": _stat_rank(st, "avg") or _stat_rank(st, "avg90") or _stat_rank(st, "avg30"),
    }


def live_edge_item(kp, cost_ratio=0.35):
    """Assemble ONE true-edge item from a live Keepa product: sell/demand/competition/category
    + an assumed cost + LIVE arbitrage (price dip) + LIVE timing (rank momentum)."""
    from ..arbitrage import signal as arb_signal
    from ..timing import momentum
    sell = keepa_sell_price(kp)
    it = to_product(kp, cost=round(sell * cost_ratio, 2)).as_item()
    arb = arb_signal(keepa_price_points(kp))
    if arb:
        it["arb_edge"] = arb.edge
    it["tim_edge"], it["_trend"] = momentum(keepa_rank_points(kp))
    return it


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
