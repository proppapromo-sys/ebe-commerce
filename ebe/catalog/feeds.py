#!/usr/bin/env python3
"""
feeds.py — 👂 EARS. Sample catalogs so every branch runs out of the box. Swap these
for your real scraper / supplier list / Seller-Central export — the organs don't care
where the dicts come from, only that they arrive.
"""
from __future__ import annotations

from ..genome import DataFeed
from .product import Product, Variant


def sample_sourcing_catalog() -> list:
    """Products you COULD source (sourcing branch reads these)."""
    return [
        Product("P1", "LED strip lights",      "home",    cost=5,  sell=22, fulfilment=4, monthly_sales=800, competition=0.4),
        Product("P2", "Phone case (generic)",  "phones",  cost=12, sell=25, fulfilment=5, monthly_sales=600, competition=0.9),
        Product("P3", "Yoga mat (premium)",    "fitness", cost=14, sell=45, fulfilment=6, monthly_sales=300, competition=0.5),
        Product("P4", "Kitchen gadget",        "kitchen", cost=8,  sell=30, fulfilment=5, monthly_sales=50,  competition=0.6),
        Product("M1", "Graphic tee (your brand)", "apparel", cost=9, sell=28, fulfilment=5, competition=0.5,
                variants=[Variant("S", "Black", monthly_sales=40), Variant("M", "Black", monthly_sales=120),
                          Variant("L", "Black", monthly_sales=90), Variant("M", "White", monthly_sales=70)]),
    ]


def sample_live_catalog() -> list:
    """SKUs you ALREADY sell — with stock + demand (pricing / restock / ads read these)."""
    return [
        Product("P1", "LED strip lights", "home", cost=5, sell=22, fulfilment=4,
                monthly_sales=800, competition=0.4, on_hand=900, lead_time_days=18, elasticity=1.8),
        Product("P3", "Yoga mat (premium)", "fitness", cost=14, sell=45, fulfilment=6,
                monthly_sales=300, competition=0.5, on_hand=120, lead_time_days=30, elasticity=1.2),
        Product("M1", "Graphic tee (your brand)", "apparel", cost=9, sell=28, fulfilment=5,
                competition=0.5, lead_time_days=21, elasticity=1.6,
                variants=[Variant("S", "Black", on_hand=15, monthly_sales=40),
                          Variant("M", "Black", on_hand=60, monthly_sales=120),
                          Variant("L", "Black", on_hand=8,  monthly_sales=90),
                          Variant("M", "White", on_hand=110, monthly_sales=70)]),
        Product("M2", "Embroidered cap", "apparel", cost=7, sell=24, fulfilment=4,
                competition=0.7, lead_time_days=25, elasticity=2.0,
                variants=[Variant("OS", "Navy", on_hand=40, monthly_sales=150),
                          Variant("OS", "Khaki", on_hand=5, monthly_sales=80)]),
    ]


class ListFeed(DataFeed):
    """Adapts a list of Products into the genome's candidate stream."""
    def __init__(self, products):
        self.products = products

    def candidates(self):
        return [p.as_item() for p in self.products]
