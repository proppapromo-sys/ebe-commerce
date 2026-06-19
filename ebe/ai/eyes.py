#!/usr/bin/env python3
"""
eyes.py — the AI EYES organ (👁️). Claude RECOGNISES reusable patterns about a product —
premium positioning, a rising trend, a saturated design, gift-ability, seasonality — instead
of only reading the numbers. Optionally looks at the product IMAGE (vision).

Caged like the Brain: the AI only NAMES what it sees. Whether a pattern earns a vote is the
genome's call — LearningEyes.trust() reads the table earned on the journal, so an AI-spotted
pattern graduates on the RECORD (real sell-through), never on the AI's say-so. Laws 3 & 4 hold.

Uses Haiku (cheap) — you may run it over thousands of products.
"""
from __future__ import annotations

import json

from ..genome import LearningEyes
from .client import ask_json, MODEL_FAST

SYSTEM = (
    "You are the EYES organ of a risk-first commerce engine. Look at a product and name the "
    "REUSABLE patterns you recognise that tend to predict whether it sells well or poorly — "
    "things like 'premium-positioning', 'trend:rising', 'saturated-design', 'giftable', "
    "'seasonal', 'commodity', 'bulky-low-margin'. Give each a direction: +1 if it tends to help "
    "sales, -1 if it tends to hurt, 0 if neutral. Name what you SEE; do not predict a price or "
    "guarantee an outcome. Prefer a few specific, reusable pattern names over many vague ones."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dir": {"type": "integer", "enum": [-1, 0, 1]},
                },
                "required": ["name", "dir"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["patterns"],
    "additionalProperties": False,
}


def _default_detect(item, images=None):
    user = ("Recognise reusable patterns for this product:\n"
            + json.dumps({k: item.get(k) for k in
                          ("id", "name", "category", "sell", "competition", "monthly_sales")}, indent=2))
    data = ask_json(SYSTEM, user, SCHEMA, model=MODEL_FAST, images=images)
    return [{"name": p["name"], "dir": int(p.get("dir", 0))} for p in (data.get("patterns") or [])]


class AIEyes(LearningEyes):
    """Drop-in Eyes: Claude proposes patterns; trust() still comes from the journal (caged)."""

    def __init__(self, trust_table=None, detect_fn=None, image_key="image_url"):
        super().__init__(trust_table)
        self._detect = detect_fn or _default_detect
        self.image_key = image_key
        self._cache = {}

    def detect(self, item):
        key = item.get("id", id(item))
        if key not in self._cache:
            imgs = [item[self.image_key]] if item.get(self.image_key) else None
            self._cache[key] = self._detect(item, imgs)
        return self._cache[key]
