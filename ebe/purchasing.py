#!/usr/bin/env python3
"""
purchasing.py — turn approved purchase orders into something you can actually SEND.

A PO sitting in the database isn't a re-buy. This groups your open POs by supplier and
renders a ready-to-email order sheet per supplier: contact line, line items, quantities,
unit cost, and the total to authorise. Pure text/Markdown — paste into an email, print,
or (later) hand to a supplier API for full hands-off ordering.

  from ebe.store import Store
  from ebe.purchasing import po_document
  print(po_document(Store("ebe.db")))
"""
from __future__ import annotations

import csv

_SUPPLIER_COLS = ("name", "email", "phone", "link", "lead_time_days", "min_order", "notes")


def load_supplier_rows(path) -> list:
    """Read a suppliers CSV (name,email,phone,link,lead_time_days,min_order,notes)."""
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            r = {"name": name}
            for k in ("email", "phone", "link", "notes"):
                if row.get(k):
                    r[k] = row[k].strip()
            for k in ("lead_time_days", "min_order"):
                v = (row.get(k) or "").strip()
                if v:
                    try:
                        r[k] = float(v) if k == "min_order" else int(float(v))
                    except ValueError:
                        pass
            out.append(r)
    return out


def orders_by_supplier(store, statuses=("draft", "ordered")) -> dict:
    """Group open POs by supplier name ('' = unassigned)."""
    groups = {}
    for status in statuses:
        for po in store.purchase_orders(status):
            groups.setdefault(po.get("supplier") or "", []).append(po)
    return groups


def po_document(store, statuses=("draft", "ordered"), title="EBE COMMAND · PURCHASE ORDERS") -> str:
    """Render every open PO as supplier-grouped order sheets (Markdown)."""
    groups = orders_by_supplier(store, statuses)
    if not groups:
        return "# %s\n\n_No open purchase orders._\n" % title
    lines = ["# %s\n" % title]
    grand = 0.0
    for supplier in sorted(groups, key=lambda s: (s == "", s.lower())):
        pos = groups[supplier]
        contact = store.supplier(supplier) if supplier else None
        head = supplier or "Unassigned supplier"
        lines.append("\n## %s" % head)
        if contact:
            bits = [contact.get("email"), contact.get("phone"), contact.get("link")]
            bits = [b for b in bits if b]
            if bits:
                lines.append("**Contact:** " + " · ".join(bits))
            if contact.get("min_order"):
                lines.append("_Minimum order: $%.0f_" % contact["min_order"])
        elif supplier:
            lines.append("_No contact on file — add it with `python -m ebe suppliers --file suppliers.csv`._")
        lines.append("")
        lines.append("| PO | SKU | Item | Qty | Unit | Total |")
        lines.append("|---|---|---|--:|--:|--:|")
        subtotal = 0.0
        for po in sorted(pos, key=lambda p: p["id"]):
            lines.append("| #%d | %s | %s | %d | $%.2f | $%.2f |"
                         % (po["id"], po["sku"], po["name"], po["qty"], po["unit_cost"], po["cash"]))
            subtotal += po["cash"]
        lines.append("| | | | | **Subtotal** | **$%.2f** |" % subtotal)
        grand += subtotal
    lines.append("\n---\n**TOTAL TO AUTHORISE: $%.2f**  ·  %d supplier(s)\n"
                 % (grand, len(groups)))
    return "\n".join(lines)
