#!/usr/bin/env python3
"""
subscriptions.py — RECURRING COMMERCE. Standing orders turn one-off buying into
predictable monthly revenue and spend:

  kind='buy'   a standing order you place on a cadence (charcoal every 14 days)
  kind='sell'  a recurring order you fulfil for a customer (another venue's supply plan)

The value of recurring commerce is the predictability — MRR (monthly recurring revenue)
on the sell side, committed spend on the buy side. When a subscription comes due, the
engine raises the buy PO (through the same vendor auction) or books the sell, then rolls
the next date forward by the cadence.

  from ebe.store import Store
  from ebe.subscriptions import summarize, run_due
"""
from __future__ import annotations

import time


def monthly_value(sub) -> float:
    """A subscription's value normalised to 30 days (qty × unit_price × 30/cadence)."""
    cad = sub.get("cadence_days") or 30
    if cad <= 0:
        return 0.0
    return (sub.get("qty") or 0) * (sub.get("unit_price") or 0) * 30.0 / cad


def mrr(subs, kind="sell") -> float:
    """Monthly recurring total for one side (sell = revenue, buy = committed spend)."""
    return round(sum(monthly_value(s) for s in subs if s.get("kind") == kind), 2)


def summarize(store, as_of=None) -> dict:
    subs = store.subscriptions(active_only=True)
    due = store.due_subscriptions(as_of)
    return {
        "active": len(subs),
        "mrr_sell": mrr(subs, "sell"),
        "mrr_buy": mrr(subs, "buy"),
        "due": due,
        "due_count": len(due),
    }


def run_due(store, as_of=None):
    """Process every due subscription, then roll it forward. Returns what was actioned.

    buy  → raise a draft PO (vendor auction picks the supplier/cost)
    sell → book the recurring revenue as an event (real cash still lands via Stripe)
    """
    as_of = time.time() if as_of is None else as_of
    actioned = []
    for sub in store.due_subscriptions(as_of):
        if sub["kind"] == "buy":
            offer = store.best_offer(sub["sku"], sub["qty"])
            unit_cost = (offer or {}).get("unit_cost") or sub.get("unit_price") or 0.0
            supplier = (offer or {}).get("supplier") or sub.get("counterparty")
            po_id = store.create_po(sub["sku"], sub["qty"], unit_cost,
                                    reason="subscription: %s" % (sub.get("name") or sub["sku"]),
                                    supplier=supplier, status="draft")
            actioned.append({"kind": "buy", "sub": sub, "po": po_id,
                             "cash": round(sub["qty"] * unit_cost, 2)})
        else:  # sell
            revenue = round(sub["qty"] * (sub.get("unit_price") or 0), 2)
            store._log("subscription_sell", sub["sku"], sub["qty"],
                       "%s · $%.2f" % (sub.get("counterparty") or "", revenue))
            from .ledger import bill_subscription
            inv = bill_subscription(store, sub, revenue, sub["next_due"])
            actioned.append({"kind": "sell", "sub": sub, "revenue": revenue, "invoice": inv})
        store.advance_subscription(sub["id"], as_of)
    if actioned:
        store._cx.commit()
    return actioned
