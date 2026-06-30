#!/usr/bin/env python3
"""
statements.py — CUSTOMER STATEMENTS. The receivables counterpart to purchasing.py:
turn open A/R into a sendable statement per customer — what they owe, line by line,
with terms and an aging flag on anything overdue. Paste into an email and collect.

  from ebe.store import Store
  from ebe.statements import statement, all_statements
  print(all_statements(Store("ebe.db")))
"""
from __future__ import annotations

import time


def open_ar_by_customer(store):
    """Group open receivables by customer name."""
    groups = {}
    for inv in store.invoices(status="open", kind="AR"):
        groups.setdefault(inv["party"] or "Customer", []).append(inv)
    return groups


def statement(store, customer_name, as_of=None) -> str:
    """A single customer's statement (Markdown)."""
    as_of = time.time() if as_of is None else as_of
    invs = [i for i in store.invoices(status="open", kind="AR") if (i["party"] or "Customer") == customer_name]
    cust = store.customer(customer_name)
    L = ["# Statement · %s" % customer_name]
    if cust:
        bits = [cust.get("email"), cust.get("phone")]
        bits = [b for b in bits if b]
        if bits:
            L.append("**Contact:** " + " · ".join(bits))
        L.append("_Terms: net %d days_" % (cust.get("terms_days") or 14))
    if not invs:
        L.append("\n_No open balance — thank you._")
        return "\n".join(L)
    L.append("")
    L.append("| Invoice | Memo | Due | Amount |")
    L.append("|---|---|---|--:|")
    total = overdue = 0.0
    for i in sorted(invs, key=lambda x: x["due_at"]):
        days = (i["due_at"] - as_of) / 86400
        due = "OVERDUE" if days < 0 else "in %.0fd" % days
        if days < 0:
            overdue += i["amount"]
        total += i["amount"]
        L.append("| #%d | %s | %s | $%.2f |" % (i["id"], i.get("memo") or "", due, i["amount"]))
    L.append("| | | **Total due** | **$%.2f** |" % total)
    if overdue:
        L.append("\n> ⚠ **$%.2f is overdue** — please remit." % overdue)
    return "\n".join(L)


def all_statements(store, as_of=None) -> str:
    """Every customer with an open balance, one statement each."""
    groups = open_ar_by_customer(store)
    if not groups:
        return "# Customer statements\n\n_No open receivables._\n"
    out, grand = [], 0.0
    for name in sorted(groups):
        out.append(statement(store, name, as_of))
        grand += sum(i["amount"] for i in groups[name])
    out.append("\n---\n**TOTAL OUTSTANDING (all customers): $%.2f** · %d customer(s)" % (grand, len(groups)))
    return "\n\n".join(out)
