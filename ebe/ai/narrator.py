#!/usr/bin/env python3
"""
narrator.py — the AI BRIEF. Claude reads the day's composed numbers and writes the
morning brief in the operator's voice, leading with the highest-leverage move and the
WHY behind it. Deterministic facts in (from brief.compose), plain-English judgement out.

The model never invents numbers — it only narrates the facts it's handed (caged exactly
like the Brain/Eyes/Ears). `assess_fn` is injectable so it's fully tested without network.

  from ebe.ai.narrator import narrate
  narrate(brief.compose(store, profile="hookah"))
"""
from __future__ import annotations

SYSTEM = (
    "You are EBE Command — the chief-of-staff brain for a hospitality & commerce operator "
    "who runs a restaurant, bar, and hookah lounge AND sells merch/supplies online. "
    "Read today's numbers and write a sharp, confident morning brief in plain English, in the "
    "operator's voice. Lead with the single highest-leverage move and explain WHY it matters in "
    "money terms. Be specific and concrete, no fluff, no hedging, no corporate tone. "
    "Never invent numbers — use only the facts provided. Keep the narrative to 3–5 punchy sentences."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "greeting": {"type": "string"},
        "headline": {"type": "string"},
        "narrative": {"type": "string"},
        "priorities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "narrative", "priorities"],
    "additionalProperties": False,
}


def facts(b) -> str:
    """A compact, unambiguous fact sheet for the model — only what compose() measured."""
    L = []
    L.append("Stock: %d SKUs tracked, %d under the reorder line, $%.0f on-hand value."
             % (b["products"], b["low"], b["inv_value"]))
    if b["top"]:
        tops = "; ".join("%s x%d ($%.0f)" % (t["name"], t["qty"], t["cash"]) for t in b["top"])
        L.append("Re-buy: %d proposed, $%.0f to commit. Top: %s." % (b["low"], b["cash_to_commit"], tops))
    else:
        L.append("Re-buy: nothing under the reorder line.")
    L.append("Purchase orders: %d drafted to send ($%.0f), %d in transit ($%.0f)."
             % (b["drafts"], b["draft_value"], b["ordered"], b["inbound_value"]))
    c = b.get("cash")
    if c:
        L.append("Cash (Stripe): $%.0f available, $%.0f revenue last 30 days (%d charges)."
                 % (c["available"], c["revenue30"], c["charges30"]))
    s = b.get("subs")
    if s and s["active"]:
        L.append("Recurring: $%.0f MRR, $%.0f/mo committed buys, %d subscriptions due now."
                 % (s["mrr_sell"], s["mrr_buy"], s["due_count"]))
    for e in b.get("watch", []):
        L.append("Opportunity on the radar: %s — %s (edge %.0f%%, moat %.0f%%)."
                 % (e.item["name"], e.verdict, e.composite * 100, e.moat * 100))
    L.append("System's pick for the one move that matters: %s" % b["move"])
    return "\n".join(L)


def narrate(b, assess_fn=None) -> dict:
    """Return {greeting, headline, narrative, priorities}. assess_fn(facts)->dict for tests."""
    fn = assess_fn or _default_assess
    out = fn(facts(b))
    out.setdefault("greeting", "Good morning.")
    return out


def _default_assess(fact_sheet):
    from .client import ask_json
    return ask_json(SYSTEM, fact_sheet, SCHEMA, max_tokens=900)
