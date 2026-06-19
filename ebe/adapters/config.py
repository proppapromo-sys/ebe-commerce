#!/usr/bin/env python3
"""
config.py — credentials, loaded from a local .env (never commit it). Pure stdlib:
a tiny KEY=VALUE parser, so there's no python-dotenv dependency. Real keys live in
.env on your machine / server; .env.example documents what's needed.
"""
from __future__ import annotations

import os

_LOADED = False


def load_env(path=".env"):
    """Read KEY=VALUE lines into the environment (existing env vars win)."""
    global _LOADED
    if not os.path.exists(path):
        _LOADED = True
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
    _LOADED = True


def get(key, default=None):
    if not _LOADED:
        load_env()
    return os.environ.get(key, default)


def require(keys):
    """Return the subset of keys that are missing/empty (for the doctor command)."""
    return [k for k in keys if not get(k)]


# Which env vars each integration needs:
NEEDS = {
    "keepa": ["KEEPA_API_KEY"],
    "amazon": ["SPAPI_REFRESH_TOKEN", "SPAPI_CLIENT_ID", "SPAPI_CLIENT_SECRET"],
    "amazon-ads": ["ADS_REFRESH_TOKEN", "ADS_CLIENT_ID", "ADS_CLIENT_SECRET", "ADS_PROFILE_ID"],
    "ai": ["ANTHROPIC_API_KEY"],
}
