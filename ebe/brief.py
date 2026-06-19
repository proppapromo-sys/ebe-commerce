#!/usr/bin/env python3
"""
brief.py — the MORNING BRIEF. One read of the whole operation, composed from the live
database: what's low, what to re-buy, what to send, what's inbound, and the one move that
matters most today. Shared by the CLI (`python -m ebe brief`) and the dashboard (/brief).

  from ebe.store import Store
  from ebe.brief import compose
  b = compose(Store("ebe.db"), profile="hookah")
"""
from __future__ import annotations


def compose(store, profile="generic", fee=None) -> dict:
    from . import autobuy
    from .purchasing import orders_by_supplier

    products = store.products()
    proposals = autobuy.plan(store)
    drafts = store.purchase_orders("draft")
    ordered = store.purchase_orders("ordered")

    cash_to_commit = sum(p["cash"] for p in proposals)
    draft_value = sum(po["cash"] for po in drafts)
    inbound_value = sum(po["cash"] for po in ordered)
    send_groups = orders_by_supplier(store, ("draft",))
    inv_value = sum((p.get("on_hand") or 0) * (p.get("cost") or 0) for p in products)
    top = sorted(proposals, key=lambda x: -x["cash"])[:3]

    watch = []
    try:
        from .branches import scout
        from . import edges as edgemod
        from .profile import PROFILES
        from .fees import AMAZON_FBA
        prof = PROFILES.get(profile) or PROFILES["generic"]
        ranked = edgemod.rank(scout.sample_market(), prof, fee or AMAZON_FBA)
        watch = [e for e in ranked if e.verdict in ("CORNER", "STRONG")][:3]
    except Exception:
        watch = []

    # the single highest-value move, in priority order
    if proposals:
        move = "Authorise the re-buys — $%.0f to keep %d SKU(s) in stock." % (cash_to_commit, len(proposals))
    elif drafts:
        move = "Send the %d drafted supplier order(s) — $%.0f to authorise." % (len(send_groups), draft_value)
    elif ordered:
        move = "Receive inbound stock as it lands (%d PO in transit)." % len(ordered)
    elif not products:
        move = "Load your catalog: python -m ebe catalog --products data/products.csv"
    else:
        move = "Stock is covered — hunt the next edge (Live Edge / Supply tabs)."

    return dict(products=len(products), low=len(proposals), proposals=proposals, top=top,
                cash_to_commit=cash_to_commit, drafts=len(drafts), draft_value=draft_value,
                send_groups=len(send_groups), ordered=len(ordered), inbound_value=inbound_value,
                inv_value=inv_value, watch=watch, move=move)


def render_text(b, date_str="") -> str:
    """JARVIS-style terminal rundown."""
    L = []
    head = "══ EBE COMMAND · MORNING BRIEF" + (" · %s" % date_str if date_str else "") + " ══"
    L.append("\n" + head)
    L.append("Good morning. Systems online.\n")
    L.append("📦 STOCK     %d SKU(s) tracked · %d under the reorder line · $%.0f on hand"
             % (b["products"], b["low"], b["inv_value"]))
    if b["top"]:
        t = b["top"][0]
        L.append("🚚 RE-BUY    %d proposed · $%.0f to commit  (top: %s %du $%.0f)"
                 % (b["low"], b["cash_to_commit"], t["name"][:24], t["qty"], t["cash"]))
    L.append("📝 TO SEND   %d supplier order(s) drafted · $%.0f   → python -m ebe po"
             % (b["send_groups"], b["draft_value"]))
    L.append("📥 INBOUND   %d PO(s) in transit · $%.0f" % (b["ordered"], b["inbound_value"]))
    for e in b["watch"]:
        L.append("🧭 WATCH     %s — %s (edge %.0f%%, moat %.0f%%)"
                 % (e.item["name"][:28], e.verdict, e.composite * 100, e.moat * 100))
    L.append("\n➡️  ONE MOVE: %s" % b["move"])
    return "\n".join(L)
