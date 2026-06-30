#!/usr/bin/env python3
"""
ledger.py — ACCOUNTS RECEIVABLE / PAYABLE. The money layer the network runs on:
who owes you (AR, from recurring sales) and who you owe (AP, from purchase orders),
netted into a real cash position with aging on what's overdue.

  AR  receivable  — a customer's subscription sale you've billed
  AP  payable     — a purchase order you've committed to a vendor

reconcile() mirrors every open/ordered PO into a payable (idempotent on 'po:ID'), so the
ledger always reflects committed spend without anyone double-entering it.

  from ebe.store import Store
  from ebe.ledger import reconcile, summarize
  reconcile(Store("ebe.db")); summarize(Store("ebe.db"))
"""
from __future__ import annotations

import time


def reconcile(store) -> int:
    """Ensure every open/ordered PO has a matching payable invoice. Returns # created."""
    created = 0
    for status in ("draft", "ordered"):
        for po in store.purchase_orders(status):
            ref = "po:%d" % po["id"]
            if store.create_invoice(po.get("supplier") or "Unassigned", po["cash"], kind="AP",
                                    due_days=(po.get("lead_time_days") or 14) if False else 14,
                                    ref=ref, memo="PO#%d · %s" % (po["id"], po.get("name") or po["sku"])):
                created += 1
    return created


def summarize(store, as_of=None) -> dict:
    as_of = time.time() if as_of is None else as_of
    open_inv = store.invoices(status="open")
    ar = [i for i in open_inv if i["kind"] == "AR"]
    ap = [i for i in open_inv if i["kind"] == "AP"]
    ar_total = round(sum(i["amount"] for i in ar), 2)
    ap_total = round(sum(i["amount"] for i in ap), 2)
    overdue = [i for i in open_inv if i["due_at"] < as_of]

    by_party = {}
    for i in open_inv:
        p = by_party.setdefault(i["party"] or "—", {"AR": 0.0, "AP": 0.0})
        p[i["kind"]] += i["amount"]

    return {
        "ar": ar_total, "ap": ap_total, "net": round(ar_total - ap_total, 2),
        "ar_count": len(ar), "ap_count": len(ap),
        "overdue": overdue, "overdue_total": round(sum(i["amount"] for i in overdue), 2),
        "by_party": by_party,
    }


def bill_subscription(store, sub, revenue, occurrence_ts):
    """Open a receivable for one fulfilled sell-subscription (idempotent per occurrence).
    Uses the customer's payment terms for the due date when the customer is on file."""
    ref = "sub:%d:%d" % (sub["id"], int(occurrence_ts))
    party = sub.get("counterparty") or "Customer"
    cust = store.customer(party)
    terms = (cust or {}).get("terms_days") or 14
    return store.create_invoice(
        party, revenue, kind="AR", due_days=terms, ref=ref,
        memo="%s · %s x%d" % (sub.get("name") or sub["sku"], sub["sku"], sub["qty"]))
