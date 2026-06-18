#!/usr/bin/env python3
"""
cli.py — run any branch from the terminal.

  python -m ebe sourcing     # which products to source (profit after fees, test batch)
  python -m ebe pricing      # reprice each SKU to its max profit-after-fees price
  python -m ebe inventory    # restock before you stock out (per apparel variant)
  python -m ebe adspend      # scale ad winners, cut the bleeders
  python -m ebe all          # run every branch once

  --place                    # hand cleared tickets to the (dry-run) execution organ
  --fees amazon-fba|amazon-apparel|shopify|etsy   default: amazon-fba

Run on YOUR data instead of the built-in samples:
  python -m ebe all       --products examples/products.csv --campaigns examples/campaigns.csv
  python -m ebe sourcing  --products my_catalog.csv
  python -m ebe adspend    --campaigns my_ads.csv
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


def _run(name, fee_model, place, products, campaigns):
    src = "CSV" if (products is not None or campaigns is not None) else "sample data"
    print("\n══ %s ══ (fees: %s · %s)" % (name.upper(), fee_model.name, src))
    if name == "sourcing":
        prods = products if products is not None else sample_sourcing_catalog()
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ebe", description="EBE Commerce — risk-first seller engine")
    ap.add_argument("branch", choices=BRANCHES + ("all",), help="which branch to run")
    ap.add_argument("--fees", choices=sorted(PRESETS), default=AMAZON_FBA.name,
                    help="marketplace fee model (default: amazon-fba)")
    ap.add_argument("--place", action="store_true", help="execute cleared tickets (dry-run)")
    ap.add_argument("--products", metavar="CSV", help="products/inventory CSV (see examples/products.csv)")
    ap.add_argument("--campaigns", metavar="CSV", help="ad campaigns CSV (see examples/campaigns.csv)")
    args = ap.parse_args(argv)

    fee_model = PRESETS[args.fees]
    products = load_products(args.products) if args.products else None
    campaigns = load_campaigns(args.campaigns) if args.campaigns else None

    names = BRANCHES if args.branch == "all" else (args.branch,)
    for name in names:
        _run(name, fee_model, args.place, products, campaigns)


if __name__ == "__main__":
    main()
