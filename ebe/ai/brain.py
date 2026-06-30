#!/usr/bin/env python3
"""
brain.py — the AI BRAIN organ (🧠). Claude estimates a product's REAL demand and how
sure it is; the genome does the rest. This is the vision: AI in place, but CAGED.

  • Claude returns: expected_monthly_sales, saturation (0..1), confidence (0..1), rationale.
  • edge = ROI-after-fees × confidence.  Low confidence shrinks the edge below the gate,
    so an unsure AI can't talk the engine into a buy.
  • Claude's demand estimate feeds the Risk organ's sizing — but the HEART still caps
    every order (test-batch, max-per-SKU). The AI never touches the caps.

The Brain only proposes a number. The Heart disposes, and the TruthMeter (real
sell-through) is what eventually earns — or revokes — the Eyes' trust. AI-free by design.

  python -m ebe sourcing --ai          # run sourcing with the AI brain (needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import json

from ..genome import Machine
from ..genome import EdgeModel
from ..fees import FeeModel, AMAZON_FBA, MERCH_APPAREL
from .client import ask_json

SYSTEM = (
    "You are the BRAIN organ of a risk-first e-commerce seller engine. Given a product a "
    "seller could source, soberly estimate its REAL monthly demand and how saturated the "
    "market is. Be conservative: when you are unsure, say so with a LOW confidence rather "
    "than guessing high — a wrong 'high confidence' costs the seller real money. You are "
    "estimating reality, not selling the product."
)

ASSESS_SCHEMA = {
    "type": "object",
    "properties": {
        "expected_monthly_sales": {"type": "number"},
        "saturation": {"type": "number"},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["expected_monthly_sales", "saturation", "confidence", "rationale"],
    "additionalProperties": False,
}


def _default_assess(p):
    """Ask Claude to assess one product. Returns the structured dict."""
    user = (
        "Assess this product as a sourcing candidate. Estimate expected_monthly_sales "
        "(units/month this seller could realistically move), saturation (0=open lane, "
        "1=brutally crowded), and your confidence (0..1) in the estimate.\n\n"
        + json.dumps({k: p.get(k) for k in ("id", "name", "category", "cost", "sell",
                                            "competition", "monthly_sales")}, indent=2)
    )
    return ask_json(SYSTEM, user, ASSESS_SCHEMA)


def _fees_for(item, default: FeeModel) -> FeeModel:
    return MERCH_APPAREL if item.get("category") == "apparel" or item.get("is_apparel") else default


class AIEdgeModel(EdgeModel):
    """🧠 mine() = ROI-after-fees × Claude's confidence; Claude's demand feeds Risk sizing."""

    def __init__(self, fee_model: FeeModel = AMAZON_FBA, assess_fn=None):
        self.fee_model = fee_model
        self.assess = assess_fn or _default_assess
        self._cache = {}

    def _read(self, p):
        pid = p.get("id", id(p))
        if pid not in self._cache:
            a = self.assess(p)
            self._cache[pid] = a
            # let the AI's demand read drive the Heart's sizing + demand gate
            p["monthly_sales"] = float(a.get("expected_monthly_sales", p.get("monthly_sales", 0)))
            p["_ai"] = a
        return self._cache[pid]

    def fair(self, p):
        return 1.0

    def mine(self, p):
        a = self._read(p)
        fm = _fees_for(p, self.fee_model)
        roi = fm.roi(p["sell"], p["cost"])
        conf = max(0.0, min(1.0, float(a.get("confidence", 0.5))))
        return roi * conf + 1.0          # edge = ROI × confidence


def build(feed, capital=2000, fee_model: FeeModel = AMAZON_FBA, assess_fn=None) -> Machine:
    """Wire the AI brain into the sourcing loop (reusing the Heart, Eyes and Hands)."""
    from ..branches.sourcing import SourcingRisk, SourcingEyes, SourcingExec
    return Machine(feed, AIEdgeModel(fee_model, assess_fn), SourcingRisk(capital),
                   SourcingEyes(), SourcingExec(fee_model), name="ai-sourcing")
