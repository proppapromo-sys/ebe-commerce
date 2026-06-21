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


def live_cash():
    """Real revenue + available balance from Stripe — None if not configured/reachable."""
    try:
        from .adapters import config
        if config.require(config.INTEGRATIONS["stripe"]["keys"]):
            return None
        from .adapters.stripe import StripeClient
        c = StripeClient()
        bal = c.balance()
        rev = c.revenue(30)
        return {"available": bal["available"], "pending": bal["pending"],
                "revenue30": rev["revenue"], "charges30": rev["charges"]}
    except Exception:
        return None


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

    from . import subscriptions as subm
    subs = subm.summarize(store)

    from . import ledger as ledmod
    ledmod.reconcile(store)
    led = ledmod.summarize(store)

    from . import shrinkage as shrinkmod
    audit = shrinkmod.summarize(store)

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
                inv_value=inv_value, watch=watch, move=move, cash=live_cash(), subs=subs, led=led,
                audit=audit)


def render_text(b, date_str="") -> str:
    """EBE Orb-style terminal rundown."""
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
    if b.get("cash"):
        c = b["cash"]
        L.append("💰 CASH (Stripe)  $%.0f available · $%.0f revenue/30d (%d charge%s)"
                 % (c["available"], c["revenue30"], c["charges30"], "" if c["charges30"] == 1 else "s"))
    sub = b.get("subs")
    if sub and sub["active"]:
        L.append("🔁 RECURRING  $%.0f MRR · $%.0f/mo committed buys · %d due now"
                 % (sub["mrr_sell"], sub["mrr_buy"], sub["due_count"]))
    ld = b.get("led")
    if ld and (ld["ar"] or ld["ap"]):
        tail = " · ⚠ $%.0f overdue" % ld["overdue_total"] if ld["overdue_total"] else ""
        L.append("📒 LEDGER  A/R $%.0f · A/P $%.0f · net $%.0f%s"
                 % (ld["ar"], ld["ap"], ld["net"], tail))
    au = b.get("audit")
    if au and (au["stockout_count"] or au["shrink_value"]):
        bits = []
        if au["stockout_count"]:
            bits.append("%d will stock out before re-buy" % au["stockout_count"])
        if au["shrink_value"]:
            bits.append("$%.0f shrinkage" % au["shrink_value"])
        L.append("🩸 LEAKS  " + " · ".join(bits))
    for e in b["watch"]:
        L.append("🧭 WATCH     %s — %s (edge %.0f%%, moat %.0f%%)"
                 % (e.item["name"][:28], e.verdict, e.composite * 100, e.moat * 100))
    L.append("\n➡️  ONE MOVE: %s" % b["move"])
    return "\n".join(L)
