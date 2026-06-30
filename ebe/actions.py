#!/usr/bin/env python3
"""
actions.py — LET EBE ACT. The agentic layer: EBE reads the live database, proposes the
day's concrete moves with their dollar impact, and executes only the ones you approve.

Propose is read-only. Execute runs exactly the action ids you hand it — nothing fires
without approval. Every action is reversible at the database level (POs are drafts you
can cancel; receivables you can void) so approval stays low-stakes.

  from ebe.store import Store
  from ebe.actions import propose, execute
  acts = propose(Store("ebe.db"))            # what EBE wants to do
  execute(Store("ebe.db"), [a["id"] for a in acts])   # do the approved ones
"""
from __future__ import annotations


def propose(store) -> list:
    """The day's moves, each with a stable id, plain label, and $ impact. Read-only."""
    from . import autobuy
    acts = []

    for prop in autobuy.plan(store):
        vendor = prop.get("supplier") or "?"
        bids = " · %d bids" % prop["bids"] if prop.get("bids", 0) > 1 else ""
        save = " · saves $%.0f" % prop["savings"] if prop.get("savings") else ""
        acts.append({
            "id": "po:%s" % prop["sku"], "kind": "rebuy",
            "label": "Raise PO · %s ×%d from %s%s%s" % (prop["name"], prop["qty"], vendor, bids, save),
            "impact": prop["cash"], "flow": "out",
        })

    for sub in store.due_subscriptions():
        if sub["kind"] == "buy":
            label = "Standing order · %s ×%d" % (sub.get("name") or sub["sku"], sub["qty"])
            flow = "out"
        else:
            label = "Bill subscription · %s ×%d → %s" % (
                sub.get("name") or sub["sku"], sub["qty"], sub.get("counterparty") or "customer")
            flow = "in"
        acts.append({
            "id": "sub:%d" % sub["id"], "kind": "subscription",
            "label": label, "impact": round(sub["qty"] * (sub.get("unit_price") or 0), 2), "flow": flow,
        })
    return acts


def execute(store, ids) -> list:
    """Run exactly the approved action ids. Returns a result per id."""
    from . import autobuy, subscriptions
    results = []
    for aid in ids:
        try:
            if aid.startswith("po:"):
                po = autobuy.raise_for(store, aid[3:])
                results.append({"id": aid, "ok": bool(po),
                                "msg": ("PO#%d raised" % po) if po else "no longer needed"})
            elif aid.startswith("sub:"):
                r = subscriptions.run_one(store, int(aid[4:]))
                if not r:
                    results.append({"id": aid, "ok": False, "msg": "not due"})
                elif r["kind"] == "buy":
                    results.append({"id": aid, "ok": True, "msg": "PO#%d raised ($%.0f)" % (r["po"], r["cash"])})
                else:
                    results.append({"id": aid, "ok": True, "msg": "billed $%.0f" % r["revenue"]})
            else:
                results.append({"id": aid, "ok": False, "msg": "unknown action"})
        except Exception as ex:
            results.append({"id": aid, "ok": False, "msg": "error: %s" % ex})
    return results


def summarize(acts) -> dict:
    """Totals for a proposed set: cash out, cash in, count."""
    out = sum(a["impact"] for a in acts if a.get("flow") == "out")
    inflow = sum(a["impact"] for a in acts if a.get("flow") == "in")
    return {"count": len(acts), "cash_out": round(out, 2), "cash_in": round(inflow, 2)}
