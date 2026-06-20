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
from .branches import sourcing, pricing, inventory, adspend, returns

BRANCHES = ("sourcing", "pricing", "inventory", "adspend", "returns")


def _maybe_apply_costs(products, args):
    """Overlay a real sku,cost sheet onto a product list (no-op without --costs)."""
    if products and getattr(args, "costs", None):
        from .costs import load_cost_sheet, apply_costs
        apply_costs(products, load_cost_sheet(args.costs))
    return products


def _run(name, fee_model, place, products, campaigns, keepa_products, ai=False, journal=None, portfolio=None, costs=None, ai_eyes=False):
    def _cost(ps):
        if costs and ps:
            from .costs import apply_costs
            apply_costs(ps, costs)
        return ps
    if name == "sourcing" and keepa_products is not None:
        prods, src = keepa_products, "Keepa LIVE"
    elif products is not None or campaigns is not None:
        prods, src = products, "CSV"
    else:
        prods, src = None, "sample data"
    if name == "sourcing" and ai:
        src += " · 🧠 AI brain"
    if name == "sourcing" and ai_eyes:
        src += " · 👁️ AI eyes"
    print("\n══ %s ══ (fees: %s · %s%s)" % (name.upper(), fee_model.name, src, " · real costs" if costs else ""))

    if name == "sourcing":
        prods = _cost(prods if prods is not None else sample_sourcing_catalog())
        if ai:
            from .ai import brain
            m = brain.build(ListFeed(prods), fee_model=fee_model)
        else:
            eyes = None
            if ai_eyes:
                from .ai.eyes import AIEyes
                eyes = AIEyes()
            m = sourcing.build(ListFeed(prods), fee_model=fee_model, eyes=eyes)
    elif name == "pricing":
        prods = _cost(products if products is not None else sample_live_catalog())
        m = pricing.build(ListFeed(prods), fee_model=fee_model)
    elif name == "inventory":
        prods = _cost(products if products is not None else sample_live_catalog())
        m = inventory.build(prods)
    elif name == "adspend":
        m = adspend.build(campaigns=campaigns, fee_model=fee_model)
    elif name == "returns":
        m = returns.build(fee_model=fee_model)
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
    print("EBE Command — integration check\n")
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
                from .ai.client import available, ping
                if not available():
                    print("  ◐ %-12s key set, but `pip install anthropic` is missing" % name)
                else:
                    ping()                      # real call — raises on a bad key / no credit
                    print("  ● %-12s OK · key valid (live ping)" % name)
            elif name == "shopify":
                from .adapters.shopify import ShopifyClient
                ShopifyClient().check()
                print("  ● %-12s OK · shop reachable" % name)
            elif name == "square":
                from .adapters.square import SquareClient
                SquareClient().check()
                print("  ● %-12s OK · locations reachable" % name)
            elif name == "stripe":
                from .adapters.stripe import StripeClient
                bal = StripeClient().balance()
                print("  ● %-12s OK · $%.0f available" % (name, bal["available"]))
            else:
                print("  ● %-12s configured" % name)
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


def _arbitrage(args):
    """LIVE temporal arbitrage via Keepa: which ASINs are cheap vs their own 90-day norm."""
    from .adapters.keepa import KeepaClient, keepa_price_points
    from . import arbitrage as arb
    asins = []
    if args.asins:
        asins = [a.strip() for a in args.asins.split(",") if a.strip()]
    elif args.asin_costs:
        from .adapters.keepa import load_asin_costs
        asins = [a for a, _, _ in load_asin_costs(args.asin_costs)]
    if not asins:
        raise SystemExit("give ASINs: --asins B0..,B0..  (or --asin-costs file.csv)")
    client = KeepaClient()

    if args.alt:                                  # cross-channel mode: Amazon (Keepa) vs alt channels
        from .arbitrage import cross_channel
        from .adapters.prices import load_alt_sources, DictPriceSource
        amazon = {}
        for kp in client.fetch(asins):
            amazon[kp.get("asin")] = keepa_price_points(kp).get("current")
        sources = [DictPriceSource("amazon", amazon)] + load_alt_sources(args.alt)
        print("\n══ EBE COMMAND · CROSS-CHANNEL ARBITRAGE ══ (channels: %s)"
              % ", ".join(s.name for s in sources))
        print("\n  identifier   buy @          sell @         gap   edge")
        hits = 0
        for asin in asins:
            r = cross_channel(asin, sources)
            if not r:
                continue
            hits += 1
            gap = (r["sell"] - r["buy"]) / r["sell"] if r["sell"] else 0
            print("  %-11s %-8s $%-6.2f %-8s $%-6.2f %3.0f%%  %3.0f%%"
                  % (asin, r["buy_channel"], r["buy"], r["sell_channel"], r["sell"], gap * 100, r["edge"] * 100))
        print("\n  %d cross-channel gap(s) found." % hits)
        return

    print("\n══ EBE COMMAND · LIVE ARBITRAGE ══ (Keepa · buy-low vs 90-day norm)")
    rows = []
    for kp in client.fetch(asins):
        sig = arb.signal(keepa_price_points(kp))
        if sig:
            rows.append((kp.get("asin", "?"), (kp.get("title") or "")[:30], sig))
    rows.sort(key=lambda r: r[2].edge, reverse=True)

    print("\n  ASIN        product                          now    avg    low   dip  spread  edge  signal")
    for asin, title, s in rows:
        print("  %-11s %-30s $%-5.2f $%-5.2f $%-5.2f %3.0f%%  %4.0f%%  %3.0f%%  %s"
              % (asin, title, s.current, s.avg or 0, s.low or 0, s.dip * 100,
                 s.spread * 100, s.edge * 100, s.verdict))
    buys = [r for r in rows if r[2].verdict == "BUY THE DIP"]
    print("\n  %d at a buy-the-dip price right now." % len(buys))
    print("  (temporal arbitrage on live Amazon data; cross-channel adds a 2nd PriceSource — see ebe/arbitrage.py)")


def _edges(args):
    """Score a market across ALL edge angles and rank by true (defensible) edge."""
    from .profile import PROFILES
    from .branches import scout
    from . import edges as edgemod
    prof = PROFILES.get(args.profile or "generic")
    if prof is None:
        raise SystemExit("unknown profile '%s' (choices: %s)" % (args.profile, ", ".join(sorted(PROFILES))))
    fee_model = PRESETS[args.fees]

    live = False
    if args.asins:
        from .adapters.base import AdapterError
        from .adapters.keepa import KeepaClient, live_edge_item
        asins = [a.strip() for a in args.asins.split(",") if a.strip()]
        try:
            client = KeepaClient()
            rows = [live_edge_item(kp, args.cost_ratio) for kp in client.fetch(asins)]
        except AdapterError as e:
            raise SystemExit("edges (live) failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)
        live = True
    else:
        rows = scout.sample_market()

    journal, learned = None, None
    if args.journal:                              # 🔁 compounding: read proven-category trust, record this run
        from .journal import Journal, category_trust
        journal = Journal(args.journal)
        learned = category_trust(journal.read())

    print("\n══ EBE COMMAND · TRUE EDGE ══ (profile: %s · %s · %s%s)"
          % (prof.name, fee_model.name, "Keepa LIVE" if live else "sample",
             " · 🔁 learned" if learned else ""))
    w = edgemod.weights_for(prof)
    print("  angle weights: " + " ".join("%s %.0f%%" % (k, v * 100) for k, v in w.items()))
    if learned:
        print("  proven categories: " + ", ".join("%s %.0f%%" % (c, t * 100)
              for c, t in sorted(learned.items(), key=lambda kv: -kv[1])))
    print("\n  product                       mrg dmd cmp adv rec tim arb | EDGE moat  verdict")
    ranked = edgemod.rank(rows, prof, fee_model, learned=learned)
    for e in ranked:
        s = e.signals
        bars = " ".join("%3.0f" % (s[k] * 100) for k in
                        ("margin", "demand", "competition", "advantage", "recurrence", "timing", "arbitrage"))
        print("  %-28s %s | %3.0f%% %3.0f%%  %s"
              % (e.item["name"][:28], bars, e.composite * 100, e.moat * 100, e.verdict))
    corner = [e for e in ranked if e.verdict == "CORNER"]
    print("\n  %d opportunit%s you can CORNER (defensible + profitable):"
          % (len(corner), "y" if len(corner) == 1 else "ies"))
    for e in corner:
        print("    🏰 %-26s edge %.0f%% · moat %.0f%%" % (e.item["name"][:26], e.composite * 100, e.moat * 100))
    if journal is not None:                       # record this run so outcomes can compound it later
        for e in ranked:
            if e.verdict in ("CORNER", "STRONG"):
                journal.record_decision("edges", e.item, 0.0, e.composite, [e.verdict])
        print("\n  recorded %d decision(s) to %s — mark outcomes (journal.record_outcome) to sharpen next run."
              % (sum(1 for e in ranked if e.verdict in ("CORNER", "STRONG")), args.journal))
    print("\n  angles: mrg=margin dmd=demand cmp=open-lane adv=your-advantage rec=recurring tim=trend arb=arbitrage")


def _ears(args):
    """AI Ears — normalize messy supplier listings into clean, scoreable Product rows."""
    if not args.file:
        raise SystemExit("--file listings.txt required (one supplier listing per line)")
    from .ai.ears import normalize_listings
    with open(args.file, encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    prods = normalize_listings(lines)

    print("\n══ EBE COMMAND · AI EARS ══ (normalized %d listing(s))\n" % len(prods))
    print("  id    name                              category    cost    sell")
    for p in prods:
        print("  %-5s %-32s %-10s $%-6.2f $%-6.2f" % (p.id, p.name[:32], p.category, p.cost, p.sell))
    if args.out:
        import csv
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "name", "category", "cost", "sell", "fulfilment", "competition"])
            for p in prods:
                w.writerow([p.id, p.name, p.category, p.cost, p.sell, p.fulfilment, p.competition])
        print("\n  → wrote %s (run: python -m ebe sourcing --products %s)" % (args.out, args.out))


def _pipeline(args):
    """AI pipeline: raw supplier listings → Ears normalize → true-edge score → cornerable shortlist."""
    if not args.file:
        raise SystemExit("--file listings.txt required (one supplier listing per line)")
    from .ai.ears import normalize_listings
    from . import edges as edgemod
    from .profile import PROFILES
    with open(args.file, encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    prods = normalize_listings(lines)
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    fee = PRESETS[args.fees]
    items = [p.as_item() for p in prods]
    ranked = edgemod.rank(items, prof, fee)

    print("\n══ EBE COMMAND · AI PIPELINE ══ (%d listings · profile %s · %s)" % (len(items), prof.name, fee.name))
    print("\n  product                        category   cost    sell   EDGE moat  verdict")
    for e in ranked:
        it = e.item
        print("  %-30s %-9s $%-6.2f $%-6.2f %3.0f%% %3.0f%%  %s"
              % (it.get("name", "?")[:30], it.get("category", "?"), it.get("cost", 0),
                 it.get("sell", 0), e.composite * 100, e.moat * 100, e.verdict))
    corner = [e for e in ranked if e.verdict == "CORNER"]
    print("\n  %d cornerable · get real sell/demand (Keepa: discover/arbitrage) for the top ones," % len(corner))
    print("  then `sourcing --asin-costs` to confirm ROI on live numbers.")


def _scout(args):
    """Survey a market through a Profile — landscape map + ranked, personalised opportunities."""
    from .profile import PROFILES
    from .branches import scout
    prof = PROFILES.get(args.profile or "generic")
    if prof is None:
        raise SystemExit("unknown profile '%s' (choices: %s)" % (args.profile, ", ".join(sorted(PROFILES))))
    fee_model = PRESETS[args.fees]
    rows = scout.sample_market()

    print("\n══ EBE COMMAND · SCOUT ══ (profile: %s · %s · appetite %s)" % (prof.name, fee_model.name, prof.appetite))
    if prof.advantages:
        print("  your edge: " + ", ".join("%s +%.0f%%" % (k, v * 100) for k, v in prof.advantages.items()))

    print("\n  LANDSCAPE (ranked by base ROI + your advantage):")
    print("  category    n  crowding   demand   ROI   your-edge   read")
    for r in scout.landscape(rows, prof, fee_model):
        read = "leaders dominate" if r["competition"] >= 0.75 else ("OPEN LANE" if r["competition"] <= 0.40 else "contested")
        print("  %-10s %2d   %4.0f%%   %6.0f/mo  %3.0f%%   %s   %s"
              % (r["category"], r["n"], r["competition"] * 100, r["demand"], r["roi"] * 100,
                 ("+%.0f%%" % (r["fit"] * 100)) if r["fit"] else "  – ", read))

    print("\n  OPPORTUNITIES to pursue (personalised gate):")
    tickets = scout.build(rows, prof, fee_model).cycle(place=True)
    print("  → %d worth pursuing for this profile." % len(tickets))


def _outcome(args):
    """Record a real result so the learning loop / compounding edge runs on actual data."""
    if not args.journal:
        raise SystemExit("--journal record.jsonl is required")
    if not args.id:
        raise SystemExit("--id <decision id> is required (e.g. --id P1)")
    from .journal import Journal
    if args.score is not None:
        score = args.score
    elif args.win:
        score = 1.0
    elif args.loss:
        score = -1.0
    else:
        raise SystemExit("say how it went: --win, --loss, or --score <number>")
    Journal(args.journal).record_outcome(args.outcome_branch or "edges", args.id, score)
    print("📓 recorded outcome: %s = %+g  →  %s (re-run with --journal to compound)"
          % (args.id, score, args.journal))


def _forecast(args):
    """Forward cash-flow: when each reorder fires and how much cash you'll need (store or venue)."""
    from . import forecast
    if args.venue:
        from .venue.sample import sample_menu, sample_consumables, sample_sales
        menu, consumables = sample_menu(), sample_consumables()
        sales = _parse_sales(args.sales) if args.sales else sample_sales()
        rows = forecast.venue_calendar(sales, menu, consumables, period_days=args.period)
        title = "CASH FORECAST · VENUE SUPPLIES"
    else:
        prods = _maybe_apply_costs(load_products(args.products) if args.products else sample_live_catalog(), args)
        rows = forecast.cash_calendar(prods)
        title = "CASH FORECAST"
    win = forecast.windows(rows)

    print("\n══ EBE COMMAND · %s ══" % title)
    print("  cash needed →  next 7d: $%-7.0f  30d: $%-7.0f  60d: $%-7.0f  90d: $%-7.0f"
          % (win[7], win[30], win[60], win[90]))
    if args.capital is not None:
        rw = forecast.runway(win, args.capital)
        parts = []
        for h in (7, 30, 60, 90):
            parts.append("%dd %s" % (h, ("OK $%.0f" % rw[h]) if rw[h] >= 0 else "SHORT $%.0f" % (-rw[h])))
        print("  vs $%.0f capital → %s" % (args.capital, "  ".join(parts)))
        short = [h for h in (7, 30, 60, 90) if rw[h] < 0]
        if short:
            print("  ⚠️  capital runs short by day %d — raise cash, slow a reorder, or trim sourcing." % short[0])
    if not rows:
        print("\n  (nothing projected to reorder — everything well-stocked)")
        return
    print("\n  when        item                          reorder   cash    (cover now)")
    for r in rows:
        when = "NOW" if r["days_until"] <= 0 else "in %4.0fd" % r["days_until"]
        print("  %-9s %-28s %5d u  $%-6.0f  %4.0fd" % (when, r["name"][:28], r["qty"], r["cash"], r["cover"]))
    print("\n  %d reorder(s) on the horizon · $%.0f total over 90 days" % (len(rows), win[90]))


def _command(args):
    """EBE COMMAND — one consolidated daily action list across every operator branch."""
    import contextlib
    import io
    fee_model = PRESETS[args.fees]
    products = load_products(args.products) if args.products else None
    campaigns = load_campaigns(args.campaigns) if args.campaigns else None
    live = _maybe_apply_costs(products if products is not None else sample_live_catalog(), args)
    src = _maybe_apply_costs(products if products is not None else sample_sourcing_catalog(), args)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):           # silence each branch; we render one report
        t_returns = returns.build(fee_model=fee_model).cycle()
        t_inv = inventory.build(live).cycle()
        t_price = pricing.build(ListFeed(live), fee_model=fee_model).cycle()
        t_ads = adspend.build(campaigns=campaigns, fee_model=fee_model).cycle()
        t_source = sourcing.build(ListFeed(src), fee_model=fee_model).cycle()

    print("\n══ EBE COMMAND · TODAY ══ (fees: %s)" % fee_model.name)

    leak = sum(s for _, s in t_returns)
    if t_returns:
        print("\n🩹 STOP THE LEAK (returns above norm):")
        for it, s in t_returns:
            print("   %-26s %3.0f%% returns · $%.0f/mo bleeding" % (it["name"][:26], it.get("_rate", 0) * 100, s))

    reorder_cash = sum(int(s) * it.get("cost", 0) for it, s in t_inv)
    if t_inv:
        print("\n🚚 REORDER (about to stock out):")
        for it, s in t_inv:
            print("   %-26s %4d units · $%.0f" % (it["name"][:26], int(s), int(s) * it.get("cost", 0)))

    uplift = sum(s for _, s in t_price)
    if t_price:
        print("\n🏷️  REPRICE (leaving money on the table):")
        for it, s in t_price:
            print("   %-26s $%.2f → $%.2f · +$%.0f/mo" % (it["name"][:26], it["sell"], it.get("_best_price", it["sell"]), s))

    if t_ads:
        print("\n📈 SCALE ADS (room under target ACOS):")
        for it, s in t_ads:
            print("   %-26s +$%.0f/mo budget" % (it["name"][:26], s))

    source_cash = sum(s for _, s in t_source)
    if t_source:
        print("\n📦 SOURCE (test batch, profit after fees):")
        for it, s in t_source:
            print("   %-26s $%.0f test batch" % (it["name"][:26], s))

    n = len(t_returns) + len(t_inv) + len(t_price) + len(t_ads) + len(t_source)
    cash_out = reorder_cash + source_cash
    print("\n  ──────────────────────────────────────────────")
    print("  %d action(s) today · cash out ≈ $%.0f (reorder + source) · monthly upside ≈ $%.0f (reprice + leak fixed)"
          % (n, cash_out, uplift + leak))
    if args.capital is not None:
        diff = args.capital - cash_out
        print("  vs $%.0f capital → %s" % (args.capital,
              ("headroom $%.0f" % diff) if diff >= 0 else "⚠️ SHORT by $%.0f — trim the list or raise cash" % (-diff)))


def _parse_sales(text):
    """'drink=500,hookah=120,takeout=85' -> {'drink':500, ...}."""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = int(float(v.strip()))
    return out


def _db_path(args):
    from .store import DEFAULT_DB
    return getattr(args, "db", None) or DEFAULT_DB


def _catalog(args):
    """Load your catalog into the database (the system of record), then show it."""
    from .store import Store
    s = Store(_db_path(args))
    if args.products:
        from .catalog.csv_io import load_store_rows
        n = s.upsert_products(load_store_rows(args.products))
        print("📥 imported %d sellable units from %s" % (n, args.products))
    elif not s.products():
        # first run with no file: seed from the sample so there's something to drive
        from .catalog.csv_io import load_store_rows
        import os
        sample = os.path.join(os.path.dirname(__file__), "..", "examples", "products.csv")
        if os.path.exists(sample):
            s.upsert_products(load_store_rows(sample))
            print("📦 seeded sample catalog (pass --products YOUR.csv to load your own)")
    prods = s.products()
    print("\n══ CATALOG · %s (%d SKUs) ══" % (s.path, len(prods)))
    print("  %-22s %8s %8s %8s %8s" % ("SKU", "on_hand", "/mo", "cost", "sell"))
    for p in prods:
        print("  %-22s %8d %8d %8.2f %8.2f"
              % (p["sku"][:22], p["on_hand"], p["monthly_sales"], p["cost"], p["sell"]))


def _rebuy(args):
    """Scan the database; raise a purchase order for every SKU under its reorder line."""
    from .store import Store
    from . import autobuy
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    proposals = autobuy.plan(s)
    if not proposals:
        print("✅ nothing under the reorder line — every SKU has cover.")
        return
    auto = getattr(args, "auto", False)
    mode = "ORDERED (hands-off)" if auto else "DRAFT (awaiting your approval)"
    print("\n══ EBE COMMAND · AUTO RE-BUY · %s ══" % mode)
    raised = autobuy.scan(s, auto=auto, budget=args.budget)
    total = sum(po["cash"] for po in raised)
    for po in raised:
        print("  🚚 PO#%-4d %-24s %5d units  $%8.2f   (%s)"
              % (po["id"], po["name"][:24], po["qty"], po["cash"], po["reason"]))
    skipped = len(proposals) - len(raised)
    tail = "  · %d skipped (budget cap $%.0f)" % (skipped, args.budget) if skipped else ""
    print("  ── %d POs · $%.2f committed%s" % (len(raised), total, tail))
    if not auto:
        print("  approve & receive when stock lands:  python -m ebe orders --receive PO#")


def _orders(args):
    """List purchase orders; approve (mark ordered) or receive (add stock back)."""
    from .store import Store
    s = Store(_db_path(args))
    if args.receive is not None:
        po = s.receive_po(args.receive)
        print("📦 received PO#%d → %+d units of %s" % (args.receive, po.get("qty", 0), po.get("name", "?")))
        return
    if args.approve is not None:
        s.mark_ordered(args.approve)
        print("✅ PO#%d marked ordered" % args.approve)
        return
    if getattr(args, "id", None) and getattr(args, "score", None) is None:
        # `orders --sale SKU --qty N` style handled via --sales? keep orders focused on POs
        pass
    pos = s.purchase_orders(status=args.status)
    label = args.status or "all"
    print("\n══ PURCHASE ORDERS · %s (%d) ══" % (label, len(pos)))
    for po in pos:
        print("  PO#%-4d %-10s %-22s %5d u  $%8.2f  %s"
              % (po["id"], po["status"], po["name"][:22], po["qty"], po["cash"], po["reason"] or ""))


def _brief(args):
    """The morning brief — the whole operation in one read, from the live database."""
    import datetime
    from .store import Store
    from . import brief as briefmod
    s = Store(_db_path(args))
    b = briefmod.compose(s, profile=args.profile or "generic", fee=PRESETS[args.fees])
    print(briefmod.render_text(b, datetime.date.today().strftime("%A %d %B %Y")))


def _suppliers(args):
    """Load a suppliers CSV into the database, then list the directory."""
    from .store import Store
    s = Store(_db_path(args))
    if args.file:
        from .purchasing import load_supplier_rows
        n = s.upsert_suppliers(load_supplier_rows(args.file))
        print("📇 imported %d supplier(s) from %s" % (n, args.file))
    sup = s.suppliers()
    print("\n══ SUPPLIERS · %s (%d) ══" % (s.path, len(sup)))
    for r in sup:
        contact = " · ".join(x for x in (r.get("email"), r.get("phone"), r.get("link")) if x)
        print("  %-22s lead %2dd  min $%-6.0f %s" % (r["name"][:22], r["lead_time_days"], r["min_order"], contact))


def _sell(args):
    """Record sales so on-hand stock drops (the consumption side of the loop)."""
    from .store import Store
    s = Store(_db_path(args))
    counts = {}
    if args.products:
        import csv as _csv
        with open(args.products, newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                sku = (row.get("sku") or row.get("id") or "").strip()
                units = (row.get("units") or row.get("qty") or row.get("monthly_sales") or "").strip()
                if sku and units:
                    try:
                        counts[sku] = int(float(units))
                    except ValueError:
                        pass
    elif args.id and args.units is not None:
        counts[args.id] = int(args.units)
    else:
        raise SystemExit("usage: ebe sell --id SKU --units N   |   ebe sell --products sales.csv (sku,units)")
    n = s.record_sales(counts)
    print("🧾 recorded sales for %d SKU(s); stock dropped. Run `python -m ebe rebuy` to see new POs." % n)


def _po(args):
    """Render open purchase orders as supplier-grouped, sendable order sheets."""
    from .store import Store
    from .purchasing import po_document
    s = Store(_db_path(args))
    statuses = (args.status,) if args.status else ("draft", "ordered")
    doc = po_document(s, statuses=statuses)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(doc)
        print("📄 wrote order sheet → %s" % args.out)
    else:
        print(doc)


def _reprice(args):
    """Competitive repricing — position each SKU vs the live market, never below floor."""
    from .store import Store
    from .repricer import reprice_catalog
    s = Store(_db_path(args))
    prods = s.products()
    if not prods:
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    prices = {}
    if getattr(args, "live", False):
        from .repricer import live_prices_by_sku
        from .adapters.keepa import KeepaClient
        from .adapters.base import AdapterError
        try:
            prices = live_prices_by_sku(prods, KeepaClient().fetch)
            n = sum(1 for v in prices.values() if v)
            print("🛰️  pulled live competitor prices for %d ASIN-mapped SKU(s) from Keepa" % n)
        except AdapterError as e:
            raise SystemExit("live reprice failed: %s\n(run `python -m ebe check`)" % e)
    elif args.alt:
        import csv as _csv
        with open(args.alt, newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                sku = (row.get("sku") or row.get("identifier") or "").strip()
                try:
                    price = float(row.get("price") or 0)
                except ValueError:
                    price = 0
                if sku and price > 0:
                    prices.setdefault(sku, []).append(price)
    strategy = args.strategy or "undercut"
    floor_roi = args.floor_roi if args.floor_roi is not None else 0.30
    recs = reprice_catalog(prods, prices, PRESETS[args.fees], floor_roi=floor_roi, strategy=strategy)
    print("\n══ EBE COMMAND · REPRICE (%s · floor ROI %.0f%% · fees %s) ══"
          % (strategy, floor_roi * 100, PRESETS[args.fees].name))
    print("  %-22s %8s %8s %8s %6s  %s" % ("SKU", "now", "→ rec", "floor", "ROI", "why"))
    for r in recs:
        flag = "⚓" if r["at_floor"] else ("↑" if r["move"] > 0 else ("↓" if r["move"] < 0 else "="))
        print("  %-22s %8.2f %8.2f %8.2f %5.0f%% %s %s"
              % (r["name"][:22], r["current"], r["recommended"], r["floor"], r["roi"] * 100, flag, r["reason"]))


def _connections(args):
    """Show every integration: what it does, whether it's configured, and where to sign up."""
    from .adapters import config
    live = [(n, m) for n, m in config.INTEGRATIONS.items() if m["status"] == "live"]
    planned = [(n, m) for n, m in config.INTEGRATIONS.items() if m["status"] == "planned"]
    print("\n══ EBE COMMAND · CONNECTIONS ══\n")
    print("LIVE (adapter built — add keys to .env to switch on):")
    for n, m in live:
        mark = "●" if not config.require(m["keys"]) else "○"
        print("  %s %-12s %s" % (mark, n, m["role"]))
        print("       sign up: %s   keys: %s" % (m["signup"], ", ".join(m["keys"])))
    print("\nPLANNED (sign up now — say the word and I build the adapter):")
    for n, m in planned:
        print("  ＋ %-12s %s" % (n, m["role"]))
        print("       sign up: %s" % m["signup"])
    print("\n● configured   ○ not yet   ＋ planned   ·   run `python -m ebe check` to validate live keys")


def _channel_client(args):
    """Build the sync client for the chosen --channel (default amazon)."""
    ch = (getattr(args, "channel", None) or "amazon").lower()
    if ch == "shopify":
        from .adapters.shopify import ShopifyClient
        return "Shopify", ShopifyClient()
    from .adapters.amazon_spapi import SpApiClient
    return "Amazon SP-API", SpApiClient(region=args.region or "na", marketplace=args.marketplace or "us")


def _sync(args):
    """Pull live channel stock (Amazon/Shopify) into the database, then show what moved."""
    from .store import Store
    from .sync import sync_stock
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    label, client = _channel_client(args)
    res = sync_stock(s, client, prices=getattr(args, "with_prices", False))
    print("\n══ EBE COMMAND · LIVE STOCK SYNC (%s) ══" % label)
    for sku, units in res["updated"]:
        print("  ✓ %-24s on_hand → %d" % (sku[:24], units))
    if res["priced"]:
        for sku, amount in res["priced"]:
            print("  $ %-24s sell → %.2f" % (sku[:24], amount))
    if res["unknown"]:
        print("  ⚠ %d SKU(s) the channel reports but not in your catalog: %s"
              % (len(res["unknown"]), ", ".join(res["unknown"][:8])))
    print("  ── %d SKUs updated. Now run:  python -m ebe rebuy" % len(res["updated"]))


def _venue(args):
    """Venue supply tracking — POS counts -> supplies consumed -> reorder."""
    from .venue import engine
    from .venue.sample import sample_menu, sample_consumables, sample_sales
    menu, consumables = sample_menu(), sample_consumables()
    if getattr(args, "square", False):
        from .adapters.square import SquareClient
        from .adapters.base import AdapterError
        try:
            sales = SquareClient().sales(days=args.period)
            print("🟦 pulled %d line-item(s) from Square (last %dd)" % (len(sales), args.period))
        except AdapterError as e:
            raise SystemExit("Square pull failed: %s\n(run `python -m ebe check`)" % e)
    else:
        sales = _parse_sales(args.sales) if args.sales else sample_sales()
    print("\n══ EBE COMMAND · VENUE SUPPLY ══")
    engine.run(sales, menu, consumables, period_days=args.period, place=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ebe", description="EBE Command — risk-first seller engine")
    ap.add_argument("branch", choices=BRANCHES + ("all", "command", "forecast", "dashboard", "check", "connections", "discover", "venue", "scout", "edges", "arbitrage", "outcome", "ears", "pipeline", "catalog", "rebuy", "orders", "sync", "suppliers", "sell", "po", "brief", "reprice"),
                    help="a branch, or: command / forecast / dashboard / check / connections / discover / venue / scout / edges / arbitrage / outcome / ears / pipeline / catalog / rebuy / orders / sync / suppliers / sell / po / brief / reprice")
    ap.add_argument("--fees", choices=sorted(PRESETS), default=AMAZON_FBA.name,
                    help="marketplace fee model (default: amazon-fba)")
    ap.add_argument("--place", action="store_true", help="execute cleared tickets (dry-run)")
    ap.add_argument("--products", metavar="CSV", help="products/inventory CSV (see examples/products.csv)")
    ap.add_argument("--costs", metavar="CSV", help="overlay real per-SKU costs (sku,cost[,fulfilment]) — see examples/costs.csv")
    ap.add_argument("--campaigns", metavar="CSV", help="ad campaigns CSV (see examples/campaigns.csv)")
    ap.add_argument("--asin-costs", metavar="CSV", dest="asin_costs",
                    help="asin,cost CSV -> LIVE sourcing via Keepa (needs KEEPA_API_KEY)")
    ap.add_argument("--ai", action="store_true",
                    help="use the Claude AI brain for sourcing (needs ANTHROPIC_API_KEY + anthropic SDK)")
    ap.add_argument("--ai-eyes", action="store_true", dest="ai_eyes",
                    help="use the Claude AI eyes for sourcing — recognise product patterns (Haiku)")
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
    # venue supply tracking
    ap.add_argument("--sales", help="venue: POS counts, e.g. 'drink=500,hookah=120,takeout=85' (default: sample)")
    ap.add_argument("--period", type=int, default=30, help="venue: days the sales counts cover (default 30)")
    # forecast / command
    ap.add_argument("--venue", action="store_true", help="forecast: project venue SUPPLY cash instead of store inventory")
    ap.add_argument("--capital", type=float, default=None, help="forecast/command: your available cash, for a runway/solvency check")
    # scout / edges
    ap.add_argument("--profile", help="scout/edges: operator profile (hookah, generic, cautious, aggressive)")
    # dashboard
    ap.add_argument("--port", type=int, default=None, help="dashboard: port (default 8765)")
    # ears
    ap.add_argument("--file", help="ears: text file of supplier listings (one per line)")
    ap.add_argument("--out", help="ears: write the normalized rows to this products CSV")
    # arbitrage
    ap.add_argument("--asins", help="arbitrage/edges: ASINs to check, e.g. 'B08VRZTHDL,B0BTD83JZR'")
    ap.add_argument("--alt", metavar="CSV", help="arbitrage: cross-channel prices CSV (channel,identifier,price)")
    # outcome (record a real result -> compounding)
    ap.add_argument("--id", help="outcome: the decision id to score (e.g. P1)")
    ap.add_argument("--score", type=float, default=None, help="outcome: numeric result (>0 = it worked)")
    ap.add_argument("--win", action="store_true", help="outcome: shorthand for --score 1")
    ap.add_argument("--loss", action="store_true", help="outcome: shorthand for --score -1")
    ap.add_argument("--outcome-branch", dest="outcome_branch", help="outcome: branch name (default: edges)")
    # database / auto re-buy
    ap.add_argument("--db", metavar="FILE", help="catalog/rebuy/orders: SQLite system-of-record (default: ebe.db or $EBE_DB)")
    ap.add_argument("--auto", action="store_true", help="rebuy: place POs hands-off (status 'ordered') instead of drafts")
    ap.add_argument("--status", help="orders: filter by status (draft|ordered|received|cancelled)")
    ap.add_argument("--approve", type=int, metavar="PO", help="orders: mark a draft PO as ordered")
    ap.add_argument("--receive", type=int, metavar="PO", help="orders: receive a PO — adds its units back into stock")
    ap.add_argument("--region", help="sync: SP-API region na|eu|fe (default na)")
    ap.add_argument("--marketplace", help="sync: marketplace us|ca|uk|de|... (default us)")
    ap.add_argument("--with-prices", action="store_true", dest="with_prices", help="sync: also pull your live listing prices")
    ap.add_argument("--units", type=int, help="sell: units sold for --id SKU (drops on-hand stock)")
    ap.add_argument("--channel", help="sync: which channel to pull from (amazon|shopify; default amazon)")
    ap.add_argument("--square", action="store_true", help="venue: pull real sales from Square POS (needs SQUARE_TOKEN)")
    ap.add_argument("--strategy", help="reprice: undercut | match | premium (default undercut)")
    ap.add_argument("--floor-roi", type=float, default=None, dest="floor_roi", help="reprice: minimum ROI after fees to defend (default 0.30)")
    ap.add_argument("--live", action="store_true", help="reprice: pull live competitor prices from Keepa (uses each SKU's asin)")
    args = ap.parse_args(argv)

    if args.max_calls is not None:
        from .adapters.base import Budget, set_budget
        set_budget(Budget(args.max_calls))      # 🪙 cap outbound API spend this run

    if args.branch == "check":
        return _check()
    if args.branch == "connections":
        return _connections(args)
    if args.branch == "outcome":
        return _outcome(args)
    if args.branch == "command":
        return _command(args)
    if args.branch == "forecast":
        return _forecast(args)
    if args.branch == "dashboard":
        from . import dashboard
        return dashboard.serve(args)
    if args.branch == "ears":
        from .adapters.base import AdapterError
        try:
            return _ears(args)
        except AdapterError as e:
            raise SystemExit("ears failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)
    if args.branch == "pipeline":
        from .adapters.base import AdapterError
        try:
            return _pipeline(args)
        except AdapterError as e:
            raise SystemExit("pipeline failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)
    if args.branch == "catalog":
        return _catalog(args)
    if args.branch == "rebuy":
        return _rebuy(args)
    if args.branch == "orders":
        return _orders(args)
    if args.branch == "suppliers":
        return _suppliers(args)
    if args.branch == "sell":
        return _sell(args)
    if args.branch == "po":
        return _po(args)
    if args.branch == "brief":
        return _brief(args)
    if args.branch == "reprice":
        return _reprice(args)
    if args.branch == "sync":
        from .adapters.base import AdapterError
        try:
            return _sync(args)
        except AdapterError as e:
            raise SystemExit("sync failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)
    if args.branch == "venue":
        return _venue(args)
    if args.branch == "scout":
        return _scout(args)
    if args.branch == "edges":
        return _edges(args)
    if args.branch == "arbitrage":
        from .adapters.base import AdapterError
        try:
            return _arbitrage(args)
        except AdapterError as e:
            raise SystemExit("arbitrage failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)
    if args.branch == "discover":
        from .adapters.base import AdapterError
        try:
            return _discover(args, PRESETS[args.fees])
        except AdapterError as e:
            raise SystemExit("discover failed: %s\n(run `python -m ebe check`, see SETUP.md)" % e)

    fee_model = PRESETS[args.fees]
    products = load_products(args.products) if args.products else None
    campaigns = load_campaigns(args.campaigns) if args.campaigns else None
    costs_sheet = None
    if args.costs:
        from .costs import load_cost_sheet
        costs_sheet = load_cost_sheet(args.costs)
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
                 ai=args.ai, journal=journal, portfolio=portfolio, costs=costs_sheet, ai_eyes=args.ai_eyes)
        except AdapterError as e:
            raise SystemExit("%s failed: %s\n(run `python -m ebe check`, see SETUP.md)" % (name, e))


if __name__ == "__main__":
    main()
