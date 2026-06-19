#!/usr/bin/env python3
"""
prices.py — cross-channel PriceSources. Buy on the cheap channel, sell on the dear one.

The Amazon side comes from Keepa (already live). A second channel makes arbitrage real:
  • DictPriceSource / load_alt_sources — drop competitor prices in a CSV (works TODAY, no key)
  • EbayPriceSource — live eBay lowest price via the Browse API (needs EBAY_OAUTH_TOKEN)

Add any channel by subclassing PriceSource.price(identifier); ebe.arbitrage.cross_channel
does the rest.

  channel,identifier,price
  walmart,B08VRZTHDL,16.40
  ebay,B08VRZTHDL,15.90
"""
from __future__ import annotations

import csv

from . import config
from .base import request_json, AdapterError
from ..arbitrage import PriceSource


class DictPriceSource(PriceSource):
    """A channel backed by an in-memory {identifier: price} map (CSV / manual)."""
    def __init__(self, name, prices):
        self.name = name
        self.prices = prices

    def price(self, identifier):
        return self.prices.get(identifier)


def load_alt_sources(path):
    """`channel,identifier,price` CSV -> one DictPriceSource per channel found."""
    by_channel = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ch = (row.get("channel") or "").strip()
            ident = (row.get("identifier") or row.get("asin") or "").strip()
            raw = (row.get("price") or "").strip()
            if not ch or not ident or not raw:
                continue
            by_channel.setdefault(ch, {})[ident] = float(raw)
    return [DictPriceSource(ch, m) for ch, m in by_channel.items()]


class EbayPriceSource(PriceSource):
    """Live eBay lowest price via the Browse API. Get a token (OAuth client-credentials) at
    developer.ebay.com and set EBAY_OAUTH_TOKEN in .env. Field mapping confirmed on first call."""
    name = "ebay"

    def __init__(self, token=None, marketplace="EBAY_US"):
        self.token = token or config.get("EBAY_OAUTH_TOKEN")
        self.marketplace = marketplace

    def price(self, query):
        if not self.token:
            raise AdapterError("EBAY_OAUTH_TOKEN not set (put it in .env)")
        data = request_json(
            "GET", "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={"Authorization": "Bearer " + self.token,
                     "X-EBAY-C-MARKETPLACE-ID": self.marketplace},
            params={"q": query, "limit": 1, "sort": "price"})
        items = data.get("itemSummaries") or []
        if not items:
            return None
        p = items[0].get("price") or {}
        return float(p["value"]) if p.get("value") else None
