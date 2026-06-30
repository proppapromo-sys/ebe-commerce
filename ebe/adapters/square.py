#!/usr/bin/env python3
"""
square.py — LIVE Square POS (your venue: real sales → consumption → auto-reorder).

Auth is a single access token (Square Developer Dashboard → your app → Access token).
Point it at a location and EBE pulls what actually rang up, so the venue's supply
reorder runs on real throughput instead of typed POS counts.

  SQUARE_TOKEN        access token (sandbox or production)
  SQUARE_LOCATION_ID  the location to read (Square → Locations)

  python -m ebe venue --square            # pull last 30d of sales from Square
"""
from __future__ import annotations

import datetime

from . import config
from .base import request_json, AdapterError

BASE = "https://connect.squareup.com/v2"
SQUARE_VERSION = "2024-01-18"


class SquareClient:
    def __init__(self, token=None, location_id=None):
        self.token = token or config.get("SQUARE_TOKEN")
        self.location_id = location_id or config.get("SQUARE_LOCATION_ID")
        if not self.token:
            raise AdapterError("Square creds missing (SQUARE_TOKEN)")

    def _headers(self):
        return {"Authorization": "Bearer " + self.token, "Square-Version": SQUARE_VERSION,
                "Content-Type": "application/json"}

    def check(self):
        """Confirms the token reaches your locations."""
        data = request_json("GET", BASE + "/locations", headers=self._headers())
        return bool(data.get("locations"))

    def orders(self, since_iso):
        """Raw orders created since an ISO timestamp."""
        body = {"query": {"filter": {"date_time_filter": {"created_at": {"start_at": since_iso}}}}}
        if self.location_id:
            body["location_ids"] = [self.location_id]
        data = request_json("POST", BASE + "/orders/search", headers=self._headers(), json_body=body)
        return data.get("orders", []) or []

    def sales(self, days=30):
        """{item_name: units} sold over the trailing window — feeds the venue engine."""
        since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return orders_to_counts(self.orders(since))


# ── pure mapping (verified against live shapes on first real call) ───────────
def orders_to_counts(orders):
    """Square orders -> {line_item_name: total_units}."""
    counts = {}
    for o in orders:
        for li in o.get("line_items", []) or []:
            name = li.get("name") or "?"
            try:
                q = int(float(li.get("quantity") or 0))
            except (TypeError, ValueError):
                q = 0
            counts[name] = counts.get(name, 0) + q
    return counts
