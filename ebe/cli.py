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
"""
from __future__ import annotations

import argparse

from .fees import PRESETS, AMAZON_FBA
from .catalog.feeds import (
    ListFeed, sample_sourcing_catalog, sample_live_catalog,
)
from .branches import sourcing, pricing, inventory, adspend

BRANCHES = ("sourcing", "pricing", "inventory", "adspend")


def _run(name, fee_model, place):
    print("\n══ %s ══ (fees: %s)" % (name.upper(), fee_model.name))
    if name == "sourcing":
        m = sourcing.build(ListFeed(sample_sourcing_catalog()), fee_model=fee_model)
    elif name == "pricing":
        m = pricing.build(ListFeed(sample_live_catalog()), fee_model=fee_model)
    elif name == "inventory":
        m = inventory.build(sample_live_catalog())
    elif name == "adspend":
        m = adspend.build(fee_model=fee_model)
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
    args = ap.parse_args(argv)

    fee_model = PRESETS[args.fees]
    names = BRANCHES if args.branch == "all" else (args.branch,)
    for name in names:
        _run(name, fee_model, args.place)


if __name__ == "__main__":
    main()
