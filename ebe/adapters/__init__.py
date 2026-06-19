"""
Live data adapters. Pure stdlib (urllib), credentials from a local .env.

  • keepa        — sourcing: live buy-box price + real monthly sales (usable today)
  • amazon_spapi — pricing/inventory: your listings, prices, FBA stock
  • amazon_ads   — adspend: campaign spend / sales / ACOS

Run `python -m ebe check` to see which integrations are wired and reachable.
"""
from . import config
from .base import AdapterError

__all__ = ["config", "AdapterError"]
