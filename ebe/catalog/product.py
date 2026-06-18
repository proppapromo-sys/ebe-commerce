#!/usr/bin/env python3
"""
product.py — what you sell. A Product carries the economics every branch reads;
for merch/apparel it splits into Variants (size × colour), each with its own stock,
because a "Large Black" stocking out is a different problem from a "Small Red".
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Variant:
    """One sellable SKU of an apparel product, e.g. Tee · L · Black."""
    size: str
    color: str
    on_hand: int = 0
    monthly_sales: float = 0.0     # units/month for THIS variant

    @property
    def sku(self) -> str:
        return "%s/%s" % (self.size, self.color)


@dataclass
class Product:
    """A thing you sell. Money in cents-free floats; tune to your real costs."""
    id: str
    name: str
    category: str               # "home", "apparel", "fitness", ...
    cost: float                 # landed unit cost (manufacture + freight + duty)
    sell: float                 # current list price
    fulfilment: float = 4.0     # flat $/unit pick-pack-ship for this item
    monthly_sales: float = 0.0  # demand at the current price (whole product)
    competition: float = 0.5    # 0 (open lane) .. 1 (saturated)
    on_hand: int = 0            # total units in stock (simple products)
    lead_time_days: int = 21    # supplier reorder lead time
    elasticity: float = 1.5     # demand sensitivity to price (for the pricing branch)
    variants: list = field(default_factory=list)   # apparel: list[Variant]

    @property
    def is_apparel(self) -> bool:
        return bool(self.variants)

    @property
    def total_on_hand(self) -> int:
        if self.variants:
            return sum(v.on_hand for v in self.variants)
        return self.on_hand

    @property
    def total_monthly_sales(self) -> float:
        if self.variants:
            return sum(v.monthly_sales for v in self.variants)
        return self.monthly_sales

    def as_item(self) -> dict:
        """Flatten into the plain dict the genome organs read."""
        d = asdict(self)
        d["monthly_sales"] = self.total_monthly_sales
        d["on_hand"] = self.total_on_hand
        d["is_apparel"] = self.is_apparel
        return d
