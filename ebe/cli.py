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


def _run(name, fee_model, place, products, campaigns, keepa_products, ai=False, journal=None, portfolio=None):
    if name == "sourcing" and keepa_products is not None:
        prods, src = keepa_products, "Keepa LIVE"
    elif products is not None or campaigns is not None:
        prods, src = products, "CSV"
    else:
        prods, src = None, "sample data"
    if name == "sourcing" and ai:
        src += " · 🧠 AI brain"
    print("\n══ %s ══ (fees: %s · %s)" % (name.upper(), fee_model.name, src))

    if name == "sourcing":
        prods = prods if prods is not None else sample_sourcing_catalog()
        if ai:
            from .ai import brain
            m = brain.build(ListFeed(prods), fee_model=fee_model)
        else:
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
    if journal is not None:
        m.journal = journal          # 📓 record decisions for the learning loop
    if portfolio is not None:
        m.risk.portfolio = portfolio  # 💰 one exposure cap shared across branches
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
            elif name == "ai":
                from .ai.client import available
                if available():
                    print("  ● %-12s OK · key set + anthropic SDK installed" % name)
                else:
                    print("  ◐ %-12s key set, but `pip install anthropic` is missing" % name)
        except Exception as e:
            print("  ✕ %-12s configured but FAILED: %s" % (name, e))
    print("\n(fill .env from .env.example — see SETUP.md)")


def _discover(args, fee_model):
    """Keepa Product Finder -> ranked shortlist of candidate products, scored after fees."""
    from .adapters.keepa import discover_candidates
    from .branches.sourcing import SourcingEdge, SourcingRisk

    print("\n══ DISCOVER ══ (Keepa Product Finder · fees: %s)" % fee_model.name)
    print("  filters: category=%s · sales≥%d/mo · $%g–$%g · sellers≤%s · cost≈%d%% of price\n"
          % (args.category or "any", args.min_sales, args.min_price, args.max_price,
             args.max_sellers if args.max_sellers is not None else "any", int(args.cost_ratio * 100)))
    prods = discover_candidates(
        category=args.category, min_monthly=args.min_sales, min_price=args.min_price,
        max_price=args.max_price, max_sellers=args.max_sellers, limit=args.limit,
        cost_ratio=args.cost_ratio)
    if not prods:
        print("  no products matched — loosen the filters (lower --min-sales, widen price, raise --max-sellers).")
        return

    edge_m, risk = SourcingEdge(fee_model), SourcingRisk(2000)
    rows = []
    for p in prods:
        item = p.as_item()
        roi = edge_m.edge(item)                     # ROI after fees at the ASSUMED cost
        ok, _, _ = risk.gate(item, roi)
        rows.append((item, roi, ok))
    rows.sort(key=lambda r: r[0]["monthly_sales"], reverse=True)

    print("   # ASIN        sold/mo  price   comp  ROI*  gate  product")
    for i, (it, roi, ok) in enumerate(rows, 1):
        print("  %2d %-11s %6.0f  $%-6.2f %3.0f%%  %3.0f%%  %s  %s"
              % (i, it["id"], it["monthly_sales"], it["sell"], it["competition"] * 100,
                 roi * 100, "✅" if ok else "— ", it["name"][:38]))
    cleared = sum(1 for _, _, ok in rows if ok)
    print("\n  %d candidate(s), %d clear the gate at the assumed cost." % (len(rows), cleared))
    print("  * ROI assumes landed cost = %d%% of sell price — get REAL supplier quotes for the ✅ ones,"
          % int(args.cost_ratio * 100))
    print("    put them in an asin,cost CSV, and re-run `python -m ebe sourcing --asin-costs ...`.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ebe", description="EBE Commerce — risk-first seller engine")
    ap.add_argument("branch", choices=BRANCHES + ("all", "check", "discover"),
                    help="which branch to run (or 'check' / 'discover')")
    ap.add_argument("--fees", choices=sorted(PRESETS), default=AMAZON_FBA.name,
                    help="marketplace fee model (default: amazon-fba)")
    ap.add_argument("--place", action="store_true", help="execute cleared tickets (dry-run)")
    ap.add_argument("--products", metavar="CSV", help="products/inventory CSV (see examples/products.csv)")
    ap.add_argument("--campaigns", metavar="CSV", help="ad campaigns CSV (see examples/campaigns.csv)")
    ap.add_argument("--asin-costs", metavar="CSV", dest="asin_costs",
                    help="asin,cost CSV -> LIVE sourcing via Keepa (needs KEEPA_API_KEY)")
    ap.add_argument("--ai", action="store_true",
                    help="use the Claude AI brain for sourcing (needs ANTHROPIC_API_KEY + anthropic SDK)")
    ap.add_argument("--journal", metavar="JSONL", help="append every cleared decision to this record (learning loop)")
    ap.add_argument("--budget", type=float, default=None, help="cap total $ committed across all cleared actions this run (portfolio exposure)")
    ap.add_argument("--max-calls", type=int, default=None, dest="max_calls", help="cap outbound API calls this run (Keepa/Anthropic/Amazon cost safety)")
    # discover filters (Keepa Product Finder)
    ap.add_argument("--category", help="discover: category (home, kitchen, health, beauty, sports, toys, pet, office, garden, baby, electronics, apparel)")
    ap.add_argument("--min-sales", type=int, default=300, dest="min_sales", help="discover: min monthly units sold (default 300)")
    ap.add_argument("--min-price", type=float, default=15.0, dest="min_price", help="discover: min sell price (default 15)")
    ap.add_argument("--max-price", type=float, default=60.0, dest="max_price", help="discover: max sell price (default 60)")
    ap.add_argument("--max-sellers", type=int, default=None, dest="max_sellers", help="discover: max competing sellers")
    ap.add_argument("--limit", type=int, default=30, help="discover: how many candidates to pull (default 30)")
    ap.add_argument("--cost-ratio", type=float, default=0.35, dest="cost_ratio", help="discover: assumed landed cost as a fraction of sell price (default 0.35)")
    args = ap.parse_args(argv)

    if args.max_calls is not None:
        from .adapters.base import Budget, set_budget
        set_budget(Budget(args.max_calls))      # 🪙 cap outbound API spend this run

    if args.branch == "check":
        return _check()
    if args.branch == "discover":
        from .adapters.base import AdapterError
        try:
            return _discover(args, PRESETS[args.fees])
        except AdapterError as e:
            raise SystemExit("discover failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)

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

    from .adapters.base import AdapterError
    journal = None
    if args.journal:
        from .journal import Journal
        journal = Journal(args.journal)
    portfolio = None
    if args.budget is not None:
        from .genome import Portfolio
        portfolio = Portfolio(args.budget)
    names = BRANCHES if args.branch == "all" else (args.branch,)
    for name in names:
        try:
            _run(name, fee_model, args.place, products, campaigns, keepa_products,
                 ai=args.ai, journal=journal, portfolio=portfolio)
        except AdapterError as e:
            raise SystemExit("%s failed: %s\n(run `python -m ebe check`, see SETUP.md)" % (name, e))


if __name__ == "__main__":
    main()
