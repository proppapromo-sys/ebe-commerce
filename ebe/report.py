#!/usr/bin/env python3
"""
report.py — THE EXECUTIVE RUNDOWN. Fuses the operational brief (stock, re-buys, cash,
ledger) with the catalog score (which products earn, which bleed) and has Claude write a
plain-English business report: what's happening, the prioritized to-do list, and which
products to push vs drop. The strategic layer on top of the daily `brief`.

The model only narrates the deterministic facts it's handed — it never invents numbers.
`assess_fn` is injectable so it's fully tested without the network.

  from ebe.store import Store
  from ebe.report import compose, write, render_text
  print(render_text(write(compose(Store("ebe.db"), profile="hookah"))))
"""
from __future__ import annotations

SYSTEM = (
    "You are EBE Command — the chief-of-staff brain for a hospitality & commerce operator. "
    "You're handed today's operating numbers AND a product-by-product profit score. Write a "
    "sharp executive business report in plain English, in the operator's voice: what the state "
    "of the business is, the few moves that matter most (ranked), and which products to push "
    "hard versus reconsider — always in money terms. Be specific and concrete. No fluff, no "
    "hedging, no corporate tone. Never invent numbers — use only the facts provided."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string", "description": "3-6 punchy sentences on the state of the business"},
        "priorities": {"type": "array", "items": {"type": "string"}, "description": "ranked action list"},
        "product_focus": {"type": "string", "description": "which products to push and which to drop, and why"},
    },
    "required": ["headline", "summary", "priorities", "product_focus"],
    "additionalProperties": False,
}


def compose(store, profile="generic", fee=None):
    """Gather the deterministic inputs: the ops brief + the catalog score."""
    from . import brief as briefmod
    from .sourcing_rank import rank_candidates, summarize
    from .profile import PROFILES
    from .fees import AMAZON_FBA
    prof = PROFILES.get(profile) or PROFILES["generic"]
    fee = fee or AMAZON_FBA
    b = briefmod.compose(store, profile=profile, fee=fee)
    items = [{"id": p["sku"], "name": p.get("name") or p["sku"], "category": p.get("category"),
              "cost": p.get("cost") or 0, "sell": p.get("sell") or 0,
              "monthly_sales": p.get("monthly_sales") or 0} for p in store.products()]
    ranked = rank_candidates(items, prof, fee)
    summ = summarize(ranked)
    winners = [r for r in ranked if r["verdict"] in ("CORNER", "STRONG")]
    dogs = [r for r in ranked if r["verdict"] == "pass" or r["net_unit"] <= 0]
    return {"brief": b, "ranked": ranked, "summary": summ,
            "winners": winners, "dogs": dogs, "fee": fee.name, "profile": prof.name}


def facts(data) -> str:
    """Compact fact sheet for the model — brief facts plus the score."""
    from .ai.narrator import facts as brief_facts
    L = [brief_facts(data["brief"])]
    s = data["summary"]
    L.append("\nCatalog score (fees %s): %d products, %d CORNER, %d STRONG, "
             "$%.0f/mo combined profit potential."
             % (data["fee"], s["count"], s["corner"], s["strong"], s["monthly_profit"]))
    for r in data["ranked"]:
        L.append("  - %s: cost $%.2f, sell $%.2f, margin %.0f%%, edge %.0f%%, %s, $%.0f/mo."
                 % (r["name"], r["cost"], r["sell"], r["margin"] * 100,
                    r["composite"] * 100, r["verdict"], r["monthly_profit"]))
    return "\n".join(L)


def write(data, assess_fn=None) -> dict:
    """Return {headline, summary, priorities, product_focus, ...} for rendering."""
    fn = assess_fn or _default_assess
    out = fn(facts(data))
    out["_data"] = data
    return out


def _default_assess(fact_sheet):
    from .ai.client import ask_json
    return ask_json(SYSTEM, fact_sheet, SCHEMA, max_tokens=1100)


def render_text(rep) -> str:
    L = ["\n══ EBE COMMAND · BUSINESS REPORT ══"]
    if rep.get("headline"):
        L.append("\n📊 %s\n" % rep["headline"])
    if rep.get("summary"):
        L.append(rep["summary"])
    if rep.get("priorities"):
        L.append("\n➡️  PRIORITIES")
        for i, pr in enumerate(rep["priorities"], 1):
            L.append("   %d. %s" % (i, pr))
    if rep.get("product_focus"):
        L.append("\n🎯 PRODUCT FOCUS\n   %s" % rep["product_focus"])
    return "\n".join(L)
