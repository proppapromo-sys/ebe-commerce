#!/usr/bin/env python3
"""
cli.py — run any branch from the terminal.

  python -m ebe sourcing     # which products to source (profit after fees, test batch)
  python -m ebe pricing      # reprice each SKU to its max profit-after-fees price
  python -m ebe inventory    # restock before you stock out (per apparel variant)
  python -m ebe adspend      # scale ad winners, cut the bleeders
  python -m ebe all          # run every branch once
  python -m ebe check        # doctor: which live integrations are wired + reachable

  --place                    # hand cleared tickets to the (dry-run) execution organ
  --fees amazon-fba|amazon-apparel|shopify|etsy   default: amazon-fba

Data sources (default = built-in sample):
  --products examples/products.csv --campaigns examples/campaigns.csv   # your CSV exports
  --asin-costs examples/asin_costs.csv   # LIVE sourcing via Keepa (needs KEEPA_API_KEY)
"""
from __future__ import annotations

import argparse

from .fees import PRESETS, AMAZON_FBA
from .catalog.feeds import (
    ListFeed, sample_sourcing_catalog, sample_live_catalog,
)
from .catalog.csv_io import load_products, load_campaigns
from .branches import sourcing, pricing, inventory, adspend

BRANCHES = ("sourcing", "pricing", "inventory", "adspend")


def _run(name, fee_model, place, products, campaigns, keepa_products):
    if name == "sourcing" and keepa_products is not None:
        prods, src = keepa_products, "Keepa LIVE"
    elif products is not None or campaigns is not None:
        prods, src = products, "CSV"
    else:
        prods, src = None, "sample data"
    print("\n══ %s ══ (fees: %s · %s)" % (name.upper(), fee_model.name, src))

    if name == "sourcing":
        prods = prods if prods is not None else sample_sourcing_catalog()
        m = sourcing.build(ListFeed(prods), fee_model=fee_model)
    elif name == "pricing":
        prods = products if products is not None else sample_live_catalog()
        m = pricing.build(ListFeed(prods), fee_model=fee_model)
    elif name == "inventory":
        prods = products if products is not None else sample_live_catalog()
        m = inventory.build(prods)
    elif name == "adspend":
        m = adspend.build(campaigns=campaigns, fee_model=fee_model)
    else:
        raise SystemExit("unknown branch: %s" % name)
    tickets = m.cycle(place=place)
    print("  → %d action(s) cleared." % len(tickets))
    return tickets


def _check():
    """Doctor: report which integrations have credentials and can reach their API."""
    from .adapters import config
    print("EBE Commerce — integration check\n")
    for name, needs in config.NEEDS.items():
        missing = config.require(needs)
        if missing:
            print("  ○ %-12s not configured (missing: %s)" % (name, ", ".join(missing)))
            continue
        try:
            if name == "keepa":
                from .adapters.keepa import KeepaClient
                left = KeepaClient().check()
                print("  ● %-12s OK · %s tokens left" % (name, left))
            elif name == "amazon":
                from .adapters.amazon_spapi import SpApiClient
                SpApiClient().check()
                print("  ● %-12s OK · access token acquired" % name)
            elif name == "amazon-ads":
                from .adapters.amazon_ads import AdsApiClient
                AdsApiClient().check()
                print("  ● %-12s OK · profiles reachable" % name)
        except Exception as e:
            print("  ✕ %-12s configured but FAILED: %s" % (name, e))
    print("\n(fill .env from .env.example — see SETUP.md)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ebe", description="EBE Commerce — risk-first seller engine")
    ap.add_argument("branch", choices=BRANCHES + ("all", "check"), help="which branch to run (or 'check')")
    ap.add_argument("--fees", choices=sorted(PRESETS), default=AMAZON_FBA.name,
                    help="marketplace fee model (default: amazon-fba)")
    ap.add_argument("--place", action="store_true", help="execute cleared tickets (dry-run)")
    ap.add_argument("--products", metavar="CSV", help="products/inventory CSV (see examples/products.csv)")
    ap.add_argument("--campaigns", metavar="CSV", help="ad campaigns CSV (see examples/campaigns.csv)")
    ap.add_argument("--asin-costs", metavar="CSV", dest="asin_costs",
                    help="asin,cost CSV -> LIVE sourcing via Keepa (needs KEEPA_API_KEY)")
    args = ap.parse_args(argv)

    if args.branch == "check":
        return _check()

    fee_model = PRESETS[args.fees]
    products = load_products(args.products) if args.products else None
    campaigns = load_campaigns(args.campaigns) if args.campaigns else None
    keepa_products = None
    if args.asin_costs:
        from .adapters.keepa import sourcing_candidates
        from .adapters.base import AdapterError
        try:
            keepa_products = sourcing_candidates(args.asin_costs)
        except AdapterError as e:
            raise SystemExit("Keepa live sourcing failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)

    names = BRANCHES if args.branch == "all" else (args.branch,)
    for name in names:
        _run(name, fee_model, args.place, products, campaigns, keepa_products)


if __name__ == "__main__":
    main()
