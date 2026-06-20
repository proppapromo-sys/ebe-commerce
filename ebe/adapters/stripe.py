#!/usr/bin/env python3
"""
stripe.py — LIVE Stripe (your real cash-in: revenue + available balance).

Auth is a single secret key (Stripe Dashboard → Developers → API keys). EBE only ever
READS — balance and succeeded charges — so the Morning Brief and the cash forecast run
on money that actually landed, not projections.

  STRIPE_SECRET_KEY   sk_live_...  (or sk_test_... while you trial)

  python -m ebe brief        # now shows real revenue + available balance when keyed
"""
from __future__ import annotations

import time

from . import config
from .base import request_json, AdapterError

BASE = "https://api.stripe.com/v1"


class StripeClient:
    def __init__(self, key=None):
        self.key = key or config.get("STRIPE_SECRET_KEY")
        if not self.key:
            raise AdapterError("Stripe creds missing (STRIPE_SECRET_KEY)")

    def _get(self, path, params=None):
        return request_json("GET", BASE + path,
                            headers={"Authorization": "Bearer " + self.key}, params=params)

    def check(self):
        """Confirms the key reaches your account."""
        return self._get("/balance") is not None

    def balance(self):
        """{available, pending} in whole currency units (Stripe reports cents)."""
        d = self._get("/balance")
        return {"available": sum_amounts(d.get("available")),
                "pending": sum_amounts(d.get("pending"))}

    def revenue(self, days=30):
        """{revenue, charges} — gross succeeded, non-refunded charges over the window."""
        since = int(time.time() - days * 86400)
        d = self._get("/charges", params={"limit": 100, "created[gte]": since})
        return charges_total(d.get("data"))


# ── pure mapping (verified against live shapes on first real call) ───────────
def sum_amounts(entries):
    """Stripe balance entries (cents) -> whole units."""
    return sum((e.get("amount") or 0) for e in (entries or [])) / 100.0


def charges_total(charges):
    """Succeeded, non-refunded charges -> {revenue, charges}."""
    total, n = 0, 0
    for c in charges or []:
        if c.get("status") == "succeeded" and not c.get("refunded"):
            total += c.get("amount") or 0
            n += 1
    return {"revenue": total / 100.0, "charges": n}
