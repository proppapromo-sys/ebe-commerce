#!/usr/bin/env python3
"""
fees.py — the marketplace "vig". Every storefront quietly taxes your sale; the only
number that matters is what lands in YOUR pocket after all of it. A FeeModel makes
that tax explicit so no branch can fool itself with a gross-margin daydream.

Apparel is its own animal: higher referral fees AND brutal return rates (people
order three sizes and keep one). MERCH_APPAREL bakes that reality in.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeeModel:
    """All fees as a fraction of the SELL price, plus a flat per-unit fulfilment cost."""
    name: str
    referral_pct: float        # marketplace cut (Amazon referral, Etsy/Shopify fees, ...)
    ad_pct: float              # ad spend needed to actually get the sale (PPC)
    return_rate: float         # fraction of revenue lost to refunds/returns
    fulfilment: float          # flat $/unit to pick, pack and ship (FBA, postage, ...)

    def fees(self, sell: float) -> float:
        """Total $ skimmed off one sale at this price."""
        return sell * (self.referral_pct + self.ad_pct + self.return_rate) + self.fulfilment

    def with_fulfilment(self, fulfilment: float) -> "FeeModel":
        """A copy of this fee model with a different flat per-unit fulfilment cost
        (e.g. a product's real 3PL pick/pack/ship fee instead of the channel default)."""
        import dataclasses
        return dataclasses.replace(self, fulfilment=float(fulfilment))

    def net_unit(self, sell: float, cost: float) -> float:
        """Profit on ONE unit after every fee. The only honest number."""
        return sell - cost - self.fees(sell)

    def roi(self, sell: float, cost: float) -> float:
        """Return on the cash you tied up in inventory (net profit / unit cost)."""
        return self.net_unit(sell, cost) / cost if cost else 0.0

    def margin(self, sell: float, cost: float) -> float:
        """Net profit as a fraction of the sell price."""
        return self.net_unit(sell, cost) / sell if sell else 0.0

    def breakeven_roas(self, sell: float, cost: float) -> float:
        """Return-on-ad-spend you must beat for ads to be worth running.
        Below this ROAS each advertised sale loses money."""
        gross_after_non_ad = sell - cost - self.fulfilment - sell * (self.referral_pct + self.return_rate)
        return sell / gross_after_non_ad if gross_after_non_ad > 0 else float("inf")


# ── Presets (tune the numbers to YOUR category — these are sane starting points) ──
AMAZON_FBA = FeeModel("amazon-fba", referral_pct=0.15, ad_pct=0.15, return_rate=0.05, fulfilment=4.0)
MERCH_APPAREL = FeeModel("amazon-apparel", referral_pct=0.17, ad_pct=0.15, return_rate=0.20, fulfilment=5.0)
SHOPIFY = FeeModel("shopify", referral_pct=0.029, ad_pct=0.20, return_rate=0.08, fulfilment=4.5)
ETSY = FeeModel("etsy", referral_pct=0.065, ad_pct=0.12, return_rate=0.05, fulfilment=3.5)
# LOCAL B2B / your-own-venue: no marketplace cut, no ads, near-zero returns, modest
# self-delivery handling. This is where bulky low-value supplies (boxes, cups, foil)
# actually make money — sell to nearby venues and deliver them yourself.
LOCAL = FeeModel("local", referral_pct=0.0, ad_pct=0.0, return_rate=0.02, fulfilment=0.75)

PRESETS = {m.name: m for m in (AMAZON_FBA, MERCH_APPAREL, SHOPIFY, ETSY, LOCAL)}


if __name__ == "__main__":
    print("FEE MODELS — net profit on a $30 item costing $8:\n")
    for name, fm in PRESETS.items():
        print("  %-16s net $%-6.2f  ROI %5.0f%%  margin %4.0f%%  breakeven-ROAS %.2f"
              % (name, fm.net_unit(30, 8), fm.roi(30, 8) * 100, fm.margin(30, 8) * 100,
                 fm.breakeven_roas(30, 8)))
