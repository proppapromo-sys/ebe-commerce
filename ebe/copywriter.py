#!/usr/bin/env python3
"""
copywriter.py — EBE writes your product descriptions. Given a catalog product, Claude
produces a Shopify-ready description (a short pitch + benefit bullets + an SEO title),
so you don't hand-write copy for every SKU. Saved straight into the catalog's
description field, which `publish --update` then pushes to the channel.

  from ebe.store import Store
  from ebe.copywriter import describe_into_store
  describe_into_store(Store("ebe.db"))           # fill in every missing description

Needs ANTHROPIC_API_KEY + the anthropic SDK (the same key `check` validates).
"""
from __future__ import annotations

import html

_SYSTEM = (
    "You are a senior DTC e-commerce copywriter. Write vivid, specific, benefit-led "
    "product copy that converts browsers into buyers. Be honest and concrete — no "
    "fabricated specs, no medical or health claims, no empty hype ('best ever', "
    "'world-class'). Match a confident, modern retail voice. Keep it tight."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string",
                        "description": "1-2 short paragraphs of selling copy, plain text"},
        "bullets": {"type": "array", "items": {"type": "string"},
                    "description": "3-5 short benefit-led bullets"},
        "seo_title": {"type": "string", "description": "<= 60 char SEO/browser title"},
    },
    "required": ["description", "bullets"],
}


def _generate(product, brand=None):
    """Raw Claude call → {description, bullets, seo_title}. Isolated for testing."""
    from .ai.client import ask_json
    facts = ["Product name: %s" % (product.get("name") or product.get("sku"))]
    if product.get("category"):
        facts.append("Category: %s" % product["category"])
    if product.get("sell"):
        facts.append("Sells for about $%.2f" % product["sell"])
    if brand:
        facts.append("Brand voice / store: %s" % brand)
    user = ("Write a Shopify product description for this item.\n\n" + "\n".join(facts)
            + "\n\nReturn description (plain text), bullets (benefit-led), and an seo_title.")
    return ask_json(_SYSTEM, user, _SCHEMA, max_tokens=900)


def _to_html(data):
    """Assemble safe Shopify body_html from the model's parts."""
    parts = []
    desc = (data.get("description") or "").strip()
    if desc:
        parts.append("<p>%s</p>" % html.escape(desc))
    bullets = [b for b in (data.get("bullets") or []) if b and b.strip()]
    if bullets:
        parts.append("<ul>%s</ul>" % "".join("<li>%s</li>" % html.escape(b.strip()) for b in bullets))
    return "".join(parts)


def describe_product(product, brand=None):
    """Generate copy for one product. Returns {description, bullets, seo_title, html}."""
    data = _generate(product, brand)
    return {"description": data.get("description", ""),
            "bullets": data.get("bullets", []),
            "seo_title": data.get("seo_title", ""),
            "html": _to_html(data)}


def describe_into_store(store, only=None, overwrite=False, brand=None) -> dict:
    """Write AI descriptions into the catalog. Skips products that already have one
    unless overwrite=True. Returns {written, skipped, failed}."""
    only = set(only) if only else None
    written, skipped, failed = [], [], []
    for p in store.products():
        sku = p["sku"]
        if only is not None and sku not in only:
            continue
        if (p.get("description") or "").strip() and not overwrite:
            skipped.append(sku)
            continue
        try:
            copy = describe_product(p, brand=brand)
            row = dict(p)                       # merge so name/price/etc. are preserved
            row["description"] = copy["html"]
            store.upsert_products([row])
            written.append(sku)
        except Exception as e:
            failed.append((sku, str(e)))
    return {"written": written, "skipped": skipped, "failed": failed}
