#!/usr/bin/env python3
"""
client.py — the single Claude client every AI organ shares.

Uses the official Anthropic SDK (claude-opus-4-8, adaptive thinking, structured
JSON output). The SDK is an OPTIONAL dependency — the core engine stays zero-install;
AI is only pulled in when you actually use a `--ai` organ. Key comes from .env
(ANTHROPIC_API_KEY), exactly like the marketplace adapters.
"""
from __future__ import annotations

import json

from ..adapters import config
from ..adapters.base import AdapterError

# The BRAIN runs the hard reasoning -> default to the most capable model.
# (High-volume Eyes/Ears organs would use claude-haiku-4-5; wire those later.)
MODEL = "claude-opus-4-8"


def get_client():
    """Return an Anthropic client, or raise a friendly AdapterError if not ready."""
    key = config.get("ANTHROPIC_API_KEY")
    if not key:
        raise AdapterError("ANTHROPIC_API_KEY not set (put it in .env)")
    try:
        import anthropic
    except ImportError:
        raise AdapterError("anthropic SDK not installed — run: pip install 'ebe-commerce[ai]' (or pip install anthropic)")
    return anthropic.Anthropic(api_key=key)


def available():
    """True if a Claude call could be made right now (key set + SDK importable)."""
    if not config.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def ask_json(system, user, schema, max_tokens=2000):
    """One structured call: returns Claude's answer parsed against `schema`."""
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":           # safety classifier declined — handle, don't crash
        raise AdapterError("Claude declined to assess this item")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text)
