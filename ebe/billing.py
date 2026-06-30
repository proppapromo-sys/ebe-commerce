#!/usr/bin/env python3
"""
billing.py — STRIPE AUTOPILOT. Stripe calls your /webhook/stripe endpoint on every payment
event; this verifies it's really Stripe (signed) and flips the tenant's subscription:

  checkout.session.completed / invoice.paid     → link customer + renew (activate)
  invoice.payment_failed / subscription.deleted → suspend (locks them out, server-side)

So once a venue signs up and pays, renewals and lapses are hands-off — no manual `tenant
--issue`. Pure stdlib (hmac); no Stripe SDK needed.

  EBE_STRIPE_WEBHOOK_SECRET   the signing secret from your Stripe webhook endpoint (whsec_…)
  EBE_CHECKOUT_URL            your Stripe Payment Link (signup redirects clients here)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

WEBHOOK_SECRET = os.environ.get("EBE_STRIPE_WEBHOOK_SECRET", "")
RENEW_DAYS = int(os.environ.get("EBE_RENEW_DAYS", "31"))   # a billing cycle + grace


def verify_signature(payload: bytes, sig_header: str, secret: str, tolerance=300, now=None):
    """Validate Stripe's 'Stripe-Signature' header (t=...,v1=...). Returns True/False."""
    if not secret or not sig_header:
        return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    t, v1 = parts.get("t"), parts.get("v1")
    if not t or not v1:
        return False
    if tolerance and abs((time.time() if now is None else now) - int(t)) > tolerance:
        return False                                       # stale → replay protection
    signed = ("%s." % t).encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def _customer(obj):
    c = obj.get("customer")
    return c.get("id") if isinstance(c, dict) else c


def handle_event(tenants, event, days=RENEW_DAYS):
    """Apply one Stripe event to the tenant registry. Returns a short action string."""
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    if etype == "checkout.session.completed":
        tid = (obj.get("client_reference_id") or obj.get("metadata", {}).get("tenant") or "").lower()
        cust = _customer(obj)
        if tid and tenants.exists(tid):
            if cust:
                tenants.link_stripe(tid, cust)
            tenants.renew(tid, days=days)
            return "activated %s" % tid
        return "checkout for unknown tenant %r" % tid

    if etype in ("invoice.paid", "invoice.payment_succeeded"):
        t = tenants.tenant_by_stripe(_customer(obj))
        if t:
            tenants.renew(t["id"], days=days)
            return "renewed %s" % t["id"]
        return "paid: customer not linked"

    if etype in ("invoice.payment_failed", "customer.subscription.deleted",
                 "customer.subscription.paused"):
        t = tenants.tenant_by_stripe(_customer(obj))
        if t:
            tenants.suspend(t["id"])
            return "suspended %s" % t["id"]
        return "lapse: customer not linked"

    return "ignored %s" % etype


def parse(payload: bytes):
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None
