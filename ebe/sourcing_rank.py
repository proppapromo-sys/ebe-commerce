#!/usr/bin/env python3
"""
sourcing_rank.py — PICK WINNERS BEFORE YOU SPEND. Feed it candidate products you're
considering (from Alibaba / Faire / Printful / a trade show) and it ranks them by true
edge AND margin-after-fees for the channel you'll sell on — with a source/pass verdict
and projected monthly profit. Optionally it funds the best ones within a test budget.

  from ebe.sourcing_rank import load_candidates, rank_candidates, fund_within_budget
"""
from __future__ import annotations

import csv

from .edges import score


def load_candidates(path) -> list:
    """Read a candidates CSV: name,category,cost,sell[,monthly_sales,competition,supplier]."""
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            if not name:
                continue
            out.append(_norm(row, name))
    return out


def _f(row, key, default=0.0):
    v = (row.get(key) or "").strip()
    try:
        return float(v) if v else float(default)
    except ValueError:
        return float(default)


def _norm(row, name):
    return {
        "name": name, "id": name,
        "category": (row.get("category") or "?").strip(),
        "cost": _f(row, "cost"), "sell": _f(row, "sell"),
        "monthly_sales": _f(row, "monthly_sales", 0),
        "competition": _f(row, "competition", 0.5),
        "supplier": (row.get("supplier") or "").strip(),
    }


def rank_candidates(items, profile=None, fee=None, learned=None) -> list:
    """Score each candidate on edge + margin-after-fees. Best projected profit first."""
    from .fees import AMAZON_FBA
    fee = fee or AMAZON_FBA
    out = []
    for it in items:
        e = score(it, profile, fee, learned=learned)
        cost, sell = it.get("cost", 0), it.get("sell", 0)
        net = fee.net_unit(sell, cost)
        ms = it.get("monthly_sales", 0) or 0
        out.append({
            "item": it, "name": it["name"], "category": it.get("category", "?"),
            "cost": cost, "sell": sell, "net_unit": round(net, 2),
            "roi": fee.roi(sell, cost), "margin": fee.margin(sell, cost),
            "monthly_profit": round(net * ms, 0),
            "composite": e.composite, "moat": e.moat, "verdict": e.verdict,
        })
    out.sort(key=lambda r: (-r["monthly_profit"], -r["composite"]))
    return out


def fund_within_budget(ranked, budget, test_units=50):
    """Pick winners to test, best-first, until the test-batch budget runs out.
    Skips losers (verdict 'pass' or non-positive margin)."""
    chosen, spent = [], 0.0
    for r in ranked:
        if r["verdict"] == "pass" or r["net_unit"] <= 0:
            continue
        batch = round(r["cost"] * test_units, 2)
        if spent + batch > budget:
            continue
        spent += batch
        chosen.append({**r, "test_units": test_units, "test_cash": batch})
    return {"chosen": chosen, "spent": round(spent, 2),
            "monthly_profit": round(sum(c["monthly_profit"] for c in chosen), 0)}


def summarize(ranked) -> dict:
    return {
        "count": len(ranked),
        "corner": sum(1 for r in ranked if r["verdict"] == "CORNER"),
        "strong": sum(1 for r in ranked if r["verdict"] == "STRONG"),
        "winners": sum(1 for r in ranked if r["verdict"] in ("CORNER", "STRONG", "TEST")),
        "monthly_profit": round(sum(r["monthly_profit"] for r in ranked if r["verdict"] != "pass"), 0),
    }
