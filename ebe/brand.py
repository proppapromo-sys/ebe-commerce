#!/usr/bin/env python3
"""
brand.py — the product's display name, in ONE place. Set EBE_BRAND to rename the whole
UI without touching code (e.g. launch as "EBE OS" today, flip to "EBE Command" later).
The EBE Orb assistant name is separate and constant.

  EBE_BRAND="EBE Command" python -m ebe dashboard
"""
from __future__ import annotations

import os

DEFAULT = "EBE OS"
ORB = "EBE Orb"


def name():
    """The product's display name (env EBE_BRAND, else the default)."""
    return (os.environ.get("EBE_BRAND") or DEFAULT).strip()


def upper():
    """Display name in caps, for HUD headers."""
    return name().upper()
