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
    if getattr(args, "out", None):
        from .sourcing_rank import write_candidates
        n = write_candidates(args.out, [it for it, _, _ in rows], category=args.category)
        print("  📝 wrote %d candidate(s) → %s   (now: python -m ebe rank --file %s --profile hookah)"
              % (n, args.out, args.out))
    print("  * ROI assumes landed cost = %d%% of sell price — get REAL supplier quotes for the ✅ ones,"
          % int(args.cost_ratio * 100))
    print("    drop them into the candidates CSV and re-run `python -m ebe rank`.")


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
    import datetime
    for po in raised:
        eta = po.get("eta")
        when = datetime.date.fromtimestamp(eta).strftime("%a %b %d") if eta else "?"
        print("  🚚 PO#%-4d %-22s %5d units  $%8.2f   arrives ~%s (%dd lead)"
              % (po["id"], po["name"][:22], po["qty"], po["cash"], when, po.get("lead_time_days") or 0))
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
    import datetime
    print("\n══ PURCHASE ORDERS · %s (%d) ══" % (label, len(pos)))
    for po in pos:
        eta = po.get("eta")
        when = datetime.date.fromtimestamp(eta).strftime("%b %d") if eta else "—"
        print("  PO#%-4d %-9s %-20s %5d u  $%8.2f  ETA %-7s %s"
              % (po["id"], po["status"], po["name"][:20], po["qty"], po["cash"], when, po.get("supplier") or ""))


def _brief(args):
    """The morning brief — the whole operation in one read, from the live database."""
    import datetime
    from .store import Store
    from . import brief as briefmod
    s = Store(_db_path(args))
    b = briefmod.compose(s, profile=args.profile or "generic", fee=PRESETS[args.fees])
    if getattr(args, "ai", False):
        from .ai.narrator import narrate
        from .adapters.base import AdapterError
        try:
            n = narrate(b)
            date = datetime.date.today().strftime("%A %d %B %Y")
            print("\n══ EBE COMMAND · AI BRIEF · %s ══" % date)
            print("\n%s %s\n" % (n.get("greeting", ""), n["headline"]))
            print(n["narrative"])
            if n.get("priorities"):
                print("\nPriorities:")
                for i, p in enumerate(n["priorities"], 1):
                    print("  %d. %s" % (i, p))
            print()
            return
        except AdapterError as e:
            print("(AI brief unavailable: %s — falling back to the standard brief)\n" % e)
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


def _act(args):
    """Let EBE act — propose the day's moves; approve with --run (all) or --id (one)."""
    from .store import Store
    from . import actions
    s = Store(_db_path(args))
    proposed = actions.propose(s)
    if not proposed:
        print("\n══ EBE COMMAND · ACT ══\n  ✓ Nothing to action — you're all clear.")
        return
    if args.run or args.id:
        ids = [args.id] if args.id else [a["id"] for a in proposed]
        print("\n══ EBE COMMAND · ACT · executing %d ══" % len(ids))
        for r in actions.execute(s, ids):
            print("  %s %-14s %s" % ("✓" if r["ok"] else "·", r["id"], r["msg"]))
        return
    summ = actions.summarize(proposed)
    print("\n══ EBE COMMAND · ACT — %d proposed · $%.0f out · $%.0f in ══"
          % (summ["count"], summ["cash_out"], summ["cash_in"]))
    for a in proposed:
        arrow = "↑in " if a.get("flow") == "in" else "↓out"
        print("  [%s] %s  %-12s $%8.0f  %s" % ("approve", arrow, a["id"], a["impact"], a["label"]))
    print("\n  approve all:  python -m ebe act --run")
    print("  approve one:  python -m ebe act --id %s" % proposed[0]["id"])


def _ledger(args):
    """Accounts receivable / payable — who owes you, who you owe, net position."""
    import time
    from .store import Store
    from . import ledger as led
    s = Store(_db_path(args))
    if args.id and (args.win or args.score is not None):
        s.mark_invoice_paid(int(args.id))
        print("✅ invoice #%s marked paid" % args.id)
    n = led.reconcile(s)                       # mirror open POs into payables
    summ = led.summarize(s)
    print("\n══ EBE COMMAND · LEDGER ══")
    if n:
        print("  (reconciled %d new payable(s) from open POs)" % n)
    print("  A/R owed to you  $%-10.2f (%d open)" % (summ["ar"], summ["ar_count"]))
    print("  A/P you owe      $%-10.2f (%d open)" % (summ["ap"], summ["ap_count"]))
    print("  NET position     $%-10.2f" % summ["net"])
    if summ["overdue"]:
        print("  ⚠ overdue: $%.2f across %d invoice(s)" % (summ["overdue_total"], len(summ["overdue"])))
    print("\n  by party:")
    for party, b in sorted(summ["by_party"].items(), key=lambda kv: -(kv[1]["AR"] + kv[1]["AP"])):
        print("    %-22s A/R $%-9.2f A/P $%-9.2f" % (party[:22], b["AR"], b["AP"]))
    open_inv = s.invoices(status="open")
    if open_inv:
        print("\n  open invoices:")
        for i in open_inv:
            days = (i["due_at"] - time.time()) / 86400
            due = "OVERDUE" if days < 0 else "in %.0fd" % days
            print("    #%-4d %-3s $%-9.2f %-20s %-8s %s"
                  % (i["id"], i["kind"], i["amount"], (i["party"] or "")[:20], due, i.get("memo") or ""))
    print("\n  mark paid:  python -m ebe ledger --id N --win")


def _subs(args):
    """Subscriptions / standing orders — recurring buy & sell, with MRR and due processing."""
    import time
    from .store import Store
    from . import subscriptions as subm
    s = Store(_db_path(args))
    if args.file:
        import csv as _csv
        now = time.time()
        n = 0
        with open(args.file, newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                sku = (row.get("sku") or "").strip()
                if not sku:
                    continue
                first_in = float(row.get("first_in_days") or 0)
                s.add_subscription(
                    sku=sku, qty=int(float(row.get("qty") or 1)),
                    cadence_days=int(float(row.get("cadence_days") or 30)),
                    kind=(row.get("kind") or "buy").strip(),
                    counterparty=(row.get("counterparty") or "").strip() or None,
                    unit_price=float(row.get("unit_price") or 0),
                    next_due=now + first_in * 86400, name=(row.get("name") or sku).strip())
                n += 1
        print("🔁 added %d subscription(s) from %s" % (n, args.file))
    if getattr(args, "run", False):
        actioned = subm.run_due(s)
        for a in actioned:
            if a["kind"] == "buy":
                print("  🚚 standing order → PO#%d  %s ×%d  $%.0f" % (a["po"], a["sub"]["sku"], a["sub"]["qty"], a["cash"]))
            else:
                print("  💵 recurring sale  %s ×%d  $%.0f → %s" % (a["sub"]["sku"], a["sub"]["qty"], a["revenue"], a["sub"].get("counterparty") or "customer"))
        if not actioned:
            print("  nothing due right now.")
    summ = subm.summarize(s)
    print("\n══ EBE COMMAND · SUBSCRIPTIONS ══")
    print("  %d active · MRR (sell) $%.0f/mo · committed buy $%.0f/mo · %d due now"
          % (summ["active"], summ["mrr_sell"], summ["mrr_buy"], summ["due_count"]))
    for sub in s.subscriptions():
        days = max(0, (sub["next_due"] - time.time()) / 86400)
        print("  %-4s %-18s ×%-4d every %3dd  $%6.2f/u  %-16s next in %.0fd"
              % (sub["kind"], (sub["name"] or sub["sku"])[:18], sub["qty"], sub["cadence_days"],
                 sub["unit_price"], (sub["counterparty"] or "")[:16], days))


def _customers(args):
    """Customer directory + their open balances."""
    from .store import Store
    s = Store(_db_path(args))
    if args.file:
        import csv as _csv
        rows = []
        with open(args.file, newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                rows.append({"name": (row.get("name") or "").strip(),
                             "email": (row.get("email") or "").strip(),
                             "phone": (row.get("phone") or "").strip(),
                             "terms_days": int(float(row.get("terms_days") or 14)),
                             "notes": (row.get("notes") or "").strip()})
        print("👥 imported %d customer(s) from %s" % (s.upsert_customers(rows), args.file))
    from .statements import open_ar_by_customer
    ar = open_ar_by_customer(s)
    print("\n══ EBE COMMAND · CUSTOMERS (%d) ══" % len(s.customers()))
    for c in s.customers():
        owed = sum(i["amount"] for i in ar.get(c["name"], []))
        contact = " · ".join(x for x in (c.get("email"), c.get("phone")) if x)
        print("  %-22s net %2dd  owes $%-9.2f %s" % (c["name"][:22], c["terms_days"], owed, contact))


def _statement(args):
    """Sendable customer statement(s) of open receivables."""
    from .store import Store
    from . import statements
    s = Store(_db_path(args))
    doc = statements.statement(s, args.id) if args.id else statements.all_statements(s)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(doc)
        print("🧾 wrote statement → %s" % args.out)
    else:
        print(doc)


def _vendors(args):
    """Vendor bidding — load competing supplier offers and show who wins each SKU."""
    from .store import Store
    s = Store(_db_path(args))
    if args.file:
        import csv as _csv
        rows = []
        with open(args.file, newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                rows.append({
                    "sku": (row.get("sku") or "").strip(),
                    "supplier": (row.get("supplier") or "").strip(),
                    "unit_cost": float(row.get("unit_cost") or 0),
                    "lead_time_days": int(float(row.get("lead_time_days") or 21)),
                    "min_qty": int(float(row.get("min_qty") or 1)),
                    "pack_size": int(float(row.get("pack_size") or 1)),
                })
        print("📨 loaded %d vendor offer(s) from %s" % (s.upsert_offers(rows), args.file))
    skus = sorted({o["sku"] for p in s.products() for o in s.offers_for(p["sku"])})
    print("\n══ EBE COMMAND · VENDOR AUCTION ══")
    if not skus:
        print("  no offers yet — load a CSV (sku,supplier,unit_cost,lead_time_days,min_qty,pack_size)")
        return
    for sku in skus:
        offers = s.offers_for(sku)
        best = s.best_offer(sku)
        print("\n  %s — %d bid(s):" % (sku, len(offers)))
        for o in offers:
            win = "🏆" if best and o["supplier"] == best["supplier"] else "  "
            print("    %s %-22s $%6.2f/u  lead %2dd  min %d  pack %d"
                  % (win, o["supplier"][:22], o["unit_cost"], o["lead_time_days"], o["min_qty"], o["pack_size"]))


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


def _shopify_auth(args):
    """One-time Shopify OAuth — capture the Admin API token into .env."""
    from .adapters.shopify_auth import authorize, REDIRECT
    from .adapters import config
    from .adapters.base import AdapterError
    print("\n══ EBE COMMAND · SHOPIFY CONNECT ══")
    print("  Make sure the app's allowed redirect URL includes: %s\n" % REDIRECT)
    try:
        token = authorize()
    except AdapterError as e:
        raise SystemExit("Shopify connect failed: %s" % e)
    config.set_env("SHOPIFY_TOKEN", token)
    print("✅ saved SHOPIFY_TOKEN to .env — now run:  python -m ebe sync --channel shopify --with-prices")


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


def _rank(args):
    """Rank candidate products to source by true edge + margin-after-fees."""
    from .sourcing_rank import load_candidates, rank_candidates, fund_within_budget, summarize
    if not args.file:
        raise SystemExit("usage: ebe rank --file candidates.csv [--fees shopify] [--profile hookah] [--budget 2000]")
    from .profile import PROFILES
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    fee = PRESETS[args.fees]
    ranked = rank_candidates(load_candidates(args.file), prof, fee)
    summ = summarize(ranked)
    print("\n══ EBE COMMAND · SOURCING RANK (%s · fees %s) ══" % (prof.name, fee.name))
    print("  %d candidate(s) · %d CORNER · %d STRONG · $%.0f/mo combined profit potential\n"
          % (summ["count"], summ["corner"], summ["strong"], summ["monthly_profit"]))
    print("  %-26s %7s %7s %6s %5s  %-7s %s" % ("product", "cost", "sell", "margin", "EDGE", "verdict", "$/mo"))
    for r in ranked:
        print("  %-26s %7.2f %7.2f %5.0f%% %4.0f%%  %-7s $%.0f"
              % (r["name"][:26], r["cost"], r["sell"], r["margin"] * 100, r["composite"] * 100, r["verdict"], r["monthly_profit"]))
    if args.budget:
        plan = fund_within_budget(ranked, args.budget)
        print("\n  💰 fund first within $%.0f test budget:" % args.budget)
        for c in plan["chosen"]:
            print("    %-26s %d units · $%.0f" % (c["name"][:26], c["test_units"], c["test_cash"]))
        print("    ── $%.0f committed → $%.0f/mo profit potential" % (plan["spent"], plan["monthly_profit"]))


def _scan(args):
    """Comb the market — sweep categories on Keepa, score, surface the best deals."""
    from .adapters.keepa import discover_candidates
    from .adapters.base import AdapterError
    from .scanner import scan
    from .profile import PROFILES
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    cats = [c.strip() for c in (args.category or "home,kitchen,health,sports").split(",") if c.strip()]

    def fetch(category=None, **kw):
        return discover_candidates(
            category=category, min_monthly=args.min_sales, min_price=args.min_price,
            max_price=args.max_price, max_sellers=args.max_sellers, limit=args.limit,
            cost_ratio=args.cost_ratio)

    print("\n══ EBE COMMAND · MARKET SCAN ══")
    print("  combing %d categor(ies): %s · sales≥%d · $%g–$%g\n"
          % (len(cats), ", ".join(cats), args.min_sales, args.min_price, args.max_price))
    try:
        deals = scan(fetch, cats, prof, limit=args.limit)
    except AdapterError as e:
        raise SystemExit("scan failed: %s\n(run `python -m ebe check`)" % e)
    if not deals:
        print("  no opportunities cleared — loosen the filters.")
        return
    print("  %-30s %-9s %6s %5s %-7s  %s" % ("product", "channel", "margin", "EDGE", "verdict", "$/mo"))
    for d in deals:
        print("  %-30s %-9s %5.0f%% %4.0f%% %-7s  $%.0f"
              % (d["name"][:30], d["best_channel"], d["margin"] * 100, d["edge"] * 100, d["verdict"], d["monthly_profit"]))
    if getattr(args, "out", None):
        from .sourcing_rank import write_candidates
        n = write_candidates(args.out, deals)
        print("\n  📝 wrote %d to %s → quote these on Alibaba, then `python -m ebe rank`" % (n, args.out))


def _bundle(args):
    """Define kits and see their margin across channels (cost = sum of components)."""
    from .store import Store
    from . import bundles as bmod
    from .channels import compare
    from .profile import PROFILES
    s = Store(_db_path(args))
    if args.file:
        n = bmod.load_into_store(s, args.file)
        print("🎁 defined %d bundle(s) from %s" % (n, args.file))
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    bl = s.bundles()
    print("\n══ EBE COMMAND · BUNDLES (%d) ══" % len(bl))
    for b in bl:
        comps = " + ".join("%d× %s" % (c["qty"], c["component_sku"]) for c in b["components"])
        print("\n  %s — %s" % (b["sku"], b["name"]))
        print("    %s" % comps)
        print("    cost $%.2f → price $%.2f" % (b["cost"], b["price"]))
        item = bmod.as_item(s, b["sku"], monthly_sales=getattr(args, "min_sales", 0) or 80)
        for r in compare(item, prof):
            if r["channel"] in ("shopify", "amazon-fba", "local"):
                print("      %-12s margin %4.0f%%  %s" % (r["channel"], r["margin"] * 100, r["verdict"]))


def _channels(args):
    """Score each candidate across ALL channels and name the best one."""
    from .sourcing_rank import load_candidates
    from .channels import compare, best_channel
    from .profile import PROFILES
    if not args.file:
        raise SystemExit("usage: ebe channels --file candidates.csv [--profile hookah]")
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    print("\n══ EBE COMMAND · BEST CHANNEL ══")
    for it in load_candidates(args.file):
        rows = compare(it, prof)
        best = best_channel(it, prof)
        print("\n  %s  (cost $%.2f · sell $%.2f)" % (it["name"], it.get("cost", 0), it.get("sell", 0)))
        for r in rows:
            star = "→" if best and r["channel"] == best["channel"] else " "
            money = ("$%+.0f/mo" % r["monthly_profit"]) if r["net_unit"] > 0 else "LOSS"
            print("    %s %-14s margin %4.0f%%  %-7s %s" % (star, r["channel"], r["margin"] * 100, r["verdict"], money))
        if best:
            print("    ✅ best: %s (%.0f%% margin)" % (best["channel"], best["margin"] * 100))
        else:
            print("    ⚠ loses money on every channel at this price")


def _count(args):
    """Record a physical count — reconciles to truth and flags shrinkage."""
    from .store import Store
    from . import shrinkage
    if not args.id or args.units is None:
        raise SystemExit("usage: ebe count --id SKU --units COUNTED")
    s = Store(_db_path(args))
    res = shrinkage.record_count(s, args.id, args.units)
    if not res:
        raise SystemExit("unknown SKU: %s" % args.id)
    print("\n══ EBE COMMAND · COUNT · %s ══" % res["name"])
    print("  expected %d · counted %d · variance %+d" % (res["expected"], res["counted"], res["variance"]))
    if res["variance"] < 0:
        print("  ⚠ shrinkage: %d units · $%.2f lost" % (-res["variance"], -res["value"]))
    elif res["variance"] > 0:
        print("  + found %d extra units (recount / late receipt)" % res["variance"])
    else:
        print("  ✓ counts match — no shrinkage")


def _audit(args):
    """Inventory health — stockout risk + shrinkage report."""
    from .store import Store
    from . import shrinkage
    s = Store(_db_path(args))
    summ = shrinkage.summarize(s)
    print("\n══ EBE COMMAND · AUDIT ══")
    print("  %d SKU(s) at stockout risk (%d will run dry before re-buy lands) · $%.2f shrinkage logged"
          % (summ["at_risk"], summ["stockout_count"], summ["shrink_value"]))
    if summ["risk"]:
        print("\n  ⏳ stockout risk (cover vs lead time):")
        print("    %-22s %8s %8s %8s  %s" % ("SKU", "on_hand", "days", "lead", "verdict"))
        for r in summ["risk"]:
            flag = "WILL STOCK OUT" if r["stockout"] else "tight"
            print("    %-22s %8d %8.0f %8d  %s" % (r["name"][:22], r["on_hand"], r["days_left"], r["lead_time"], flag))
    if summ["shrink"]["by_sku"]:
        print("\n  🩸 shrinkage by SKU:")
        for b in summ["shrink"]["by_sku"]:
            print("    %-22s %5d units  $%.2f" % (b["name"][:22], b["units"], b["value"]))
    print("\n  record a count:  python -m ebe count --id SKU --units COUNTED")


def _sync(args):
    """Pull live channel stock (Amazon/Shopify) into the database, then show what moved."""
    from .store import Store
    from .sync import sync_stock, sync_all, configured_channels
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    prices = getattr(args, "with_prices", False)
    if (getattr(args, "channel", None) or "").lower() == "all":
        chans = configured_channels()
        print("\n══ EBE COMMAND · SYNC ALL CHANNELS ══")
        if not chans:
            print("  no channels configured — add Amazon/Shopify keys to .env (python -m ebe connections)")
            return
        res = sync_all(s, prices=prices, region=args.region or "na", marketplace=args.marketplace or "us")
        total = 0
        for name, r in res.items():
            if "error" in r:
                print("  ✕ %-9s %s" % (name, r["error"]))
            else:
                total += len(r["updated"])
                print("  ● %-9s %d SKUs updated · %d unknown" % (name, len(r["updated"]), len(r["unknown"])))
        print("  ── %d SKUs synced across %d channel(s). Now:  python -m ebe rebuy" % (total, len(res)))
        return
    label, client = _channel_client(args)
    res = sync_stock(s, client, prices=prices)
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


def _autopilot(args):
    """The self-running loop: sync → re-buy → (optional) reprice, every N minutes."""
    import time as _time
    from .store import Store
    from . import autopilot
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    every = args.every or 60
    cycles = args.cycles
    print("\n══ EBE COMMAND · AUTOPILOT ══")
    print("  every %dm · %s · re-buys as %s%s"
          % (every, ("%d cycle(s)" % cycles) if cycles else "running forever (Ctrl-C to stop)",
             "ORDERS" if args.auto else "drafts",
             " · repricing live" if args.reprice else ""))

    def show(n, r):
        stamp = _time.strftime("%H:%M:%S")
        line = ("  [%s] #%d  sync %d/%dch · %d draft(s) $%.0f"
                % (stamp, n, r["synced"], r["channels"], r["drafts"], r["cash"]))
        if r["repriced"]:
            line += " · repriced %d" % r["repriced"]
        if r["errors"]:
            line += "  ⚠ " + "; ".join(r["errors"][:2])
        print(line)

    try:
        autopilot.run(s, every_minutes=every, cycles=cycles, on_cycle=show,
                      prices=getattr(args, "with_prices", False), auto=args.auto,
                      budget=args.budget, reprice=args.reprice,
                      strategy=args.strategy or "undercut",
                      floor_roi=args.floor_roi if args.floor_roi is not None else 0.30,
                      region=args.region or "na", marketplace=args.marketplace or "us")
    except KeyboardInterrupt:
        print("\n  autopilot stopped. Review drafts:  python -m ebe orders --status draft")


def _status(args):
    """One screen: is my shop running? Connections, autopilot freshness, what's pending."""
    from .store import Store
    from . import status
    s = Store(_db_path(args))
    print(status.render_text(status.compose(s)))


def _add(args):
    """Add or update one catalog product — no CSV needed. Partial: only given fields change."""
    from .store import Store
    if not getattr(args, "sku", None):
        raise SystemExit(
            'usage: ebe add --sku COCO-CHARCOAL-1.2KG --name "Coconut Charcoal" '
            "--cost 3 --sell 14.99 [--on-hand 100] [--monthly 1000] [--supplier X] "
            "[--lead-time 21] [--asin B0...] [--category ...]")
    s = Store(_db_path(args))
    sku = args.sku.strip()
    existing = s.product(sku)
    existed = bool(existing)
    row = dict(existing) if existing else {}   # preserve untouched fields on update
    row["sku"] = sku
    for attr, col in (("name", "name"), ("category", "category"), ("cost", "cost"),
                      ("sell", "sell"), ("on_hand", "on_hand"), ("monthly", "monthly_sales"),
                      ("supplier", "supplier"), ("lead_time", "lead_time_days"), ("asin", "asin"),
                      ("description", "description"), ("image", "image_url")):
        val = getattr(args, attr, None)
        if val is not None:
            row[col] = val
    s.upsert_products([row])
    p = s.product(sku)
    print("\n══ EBE COMMAND · CATALOG %s ══" % ("UPDATED" if existed else "ADDED"))
    print("  %s  %s" % (sku, p.get("name")))
    print("  cost $%.2f · sell $%.2f · on_hand %d · %d/mo"
          % (p.get("cost") or 0, p.get("sell") or 0,
             p.get("on_hand") or 0, p.get("monthly_sales") or 0))
    print("\n  Next:  python -m ebe publish --channel shopify   (list it on your store)")


def _import(args):
    """Bulk-import pasted supplier listings into the catalog (AI Ears parses each)."""
    from .store import Store
    from . import importer
    if getattr(args, "text", None):
        text = args.text
    elif getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    else:
        raise SystemExit('usage: ebe import --file listings.txt   (or --text "listing one\\nlisting two")')
    listings = importer.split_listings(text)
    if not listings:
        raise SystemExit("no listings found in the input")
    s = Store(_db_path(args))
    print("\n══ EBE COMMAND · BULK IMPORT ══")
    print("  parsing %d listing(s) with AI ears …" % len(listings))
    res = importer.import_listings(s, listings)
    for sku, name in res["created"]:
        print("  ＋ %-26s %s" % (sku, name[:40]))
    for raw, err in res["failed"]:
        print("  ✕ %-26s %s" % (raw[:26], err[:50]))
    print("  ── %d imported · %d failed" % (len(res["created"]), len(res["failed"])))
    if res["created"]:
        print("  Next:  python -m ebe describe   then   python -m ebe publish --channel shopify")


def _describe(args):
    """Have Claude write product descriptions into the catalog (needs ANTHROPIC_API_KEY)."""
    from .store import Store
    from . import copywriter
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe add ...` or load a CSV first")
    only = [args.sku] if getattr(args, "sku", None) else None
    overwrite = getattr(args, "overwrite", False)
    print("\n══ EBE COMMAND · AI DESCRIPTIONS ══")
    print("  Writing copy with Claude%s …" % (" (overwriting)" if overwrite else " for products missing one"))
    res = copywriter.describe_into_store(s, only=only, overwrite=overwrite)
    for sku in res["written"]:
        print("  ✓ wrote     %s" % sku)
    for sku in res["skipped"]:
        print("  = has one   %s  (use --overwrite to redo)" % sku)
    for sku, err in res["failed"]:
        print("  ✕ failed    %s — %s" % (sku, err[:80]))
    print("  ── %d written · %d skipped · %d failed" % (len(res["written"]), len(res["skipped"]), len(res["failed"])))
    if res["written"]:
        print("  Now push them live:  python -m ebe publish --channel shopify --update")


def _publish(args):
    """Push the EBE catalog to a sales channel — create what's missing (matched by SKU)."""
    from .store import Store
    from .publish import publish_catalog
    ch = (getattr(args, "channel", None) or "shopify").lower()
    if ch != "shopify":
        raise SystemExit("publish currently supports --channel shopify")
    from .adapters.shopify import ShopifyClient
    s = Store(_db_path(args))
    if not s.products():
        raise SystemExit("no catalog yet — run `python -m ebe catalog --products YOUR.csv` first")
    set_stock = getattr(args, "stock", False)
    update = getattr(args, "update", False)
    print("\n══ EBE COMMAND · PUBLISH → SHOPIFY ══")
    res = publish_catalog(s, ShopifyClient(), set_stock=set_stock, update=update)
    for sku in res["created"]:
        print("  ＋ created   %s" % sku)
    for sku in res.get("updated", []):
        print("  ↻ updated   %s" % sku)
    for sku in res["skipped"]:
        print("  = already   %s%s" % (sku, "" if update else "  (use --update to refresh it)"))
    for sku, err in res["failed"]:
        print("  ✕ failed    %s — %s" % (sku, err))
    print("  ── %d created · %d updated · %d unchanged · %d failed%s"
          % (len(res["created"]), len(res.get("updated", [])), len(res["skipped"]), len(res["failed"]),
             "" if set_stock else "  (untracked — add --stock to push on-hand)"))
    if res["created"] or res.get("updated"):
        print("  Now run:  python -m ebe sync --channel shopify --with-prices")


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


def _license(args):
    """Licensing — owner mints tokens; anyone can check status."""
    from . import license as lic
    if args.keygen:
        priv = lic.generate_keypair()
        lic.save_keypair(priv)
        print("🔑 EBE owner keypair generated.")
        print("   private key → %s   ⚠ KEEP SECRET — never share or commit this" % lic.OWNER_KEY)
        print("   public key  → %s   ship this file inside the client's copy of EBE" % lic.PUBLIC_KEY)
        print("\n   You are now the owner — EBE runs free for you. Issue a client a license with:")
        print("     python -m ebe license --issue \"Their Venue\" --days 30")
        return
    if args.issue:
        priv = lic.load_private()
        if not priv:
            raise SystemExit("no owner key found — run `python -m ebe license --keygen` first")
        token = lic.issue(args.issue, args.days, priv)
        print("🎟  EBE license · %s · %d days\n" % (args.issue, args.days))
        print(token)
        print("\n   Send this token to the client. They activate it with:")
        print("     setx EBE_LICENSE \"%s...\"   (or save it to a file named license.key)" % token[:14])
        return
    st = lic.status()
    icon = {"owner": "👑", "licensed": "✅", "unlicensed": "⛔", "open": "🔓"}.get(st["state"], "•")
    print("%s EBE license: %s — %s" % (icon, st["state"].upper(), st["msg"]))


def _tenant(args):
    """Owner admin for the hosted SaaS — create / renew / suspend client venues."""
    from .tenancy import Tenants
    tn = Tenants()
    if args.keygen:                                    # reuse --keygen as "create"? no — use --issue
        pass
    if args.issue:                                     # create or renew a tenant: --issue ID
        tid = args.issue.strip().lower()
        if tn.tenant(tid):
            tn.renew(tid, days=args.days)
            print("🔁 renewed %s — %s" % (tid, tn.status_line(tid)))
        else:
            pw = args.id or "changeme"
            tn.create_tenant(tid, args.profile or tid, pw, days=args.days)
            print("👤 created tenant %s (password: %s) — %s" % (tid, pw, tn.status_line(tid)))
            print("   they sign in at the host server's /login")
        return
    if args.score is not None and args.id:             # not used
        pass
    print("\n══ EBE HOST · TENANTS ══")
    for t in tn.list_tenants():
        print("  %-14s %-22s %s" % (t["id"], t["name"][:22], tn.status_line(t["id"])))
    print("\n  create/renew:  python -m ebe tenant --issue cloud9 --id <password> --days 30")
    print("  run server:    python -m ebe host --port 8080")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ebe", description="EBE Command — risk-first seller engine")
    ap.add_argument("branch", choices=BRANCHES + ("all", "command", "forecast", "dashboard", "storefront", "check", "connections", "shopify-auth", "discover", "venue", "scout", "edges", "arbitrage", "outcome", "ears", "pipeline", "catalog", "rebuy", "orders", "sync", "suppliers", "sell", "po", "brief", "reprice", "vendors", "subs", "ledger", "act", "customers", "statement", "count", "audit", "rank", "channels", "bundle", "scan", "license", "host", "tenant", "autopilot", "status", "publish", "add", "describe", "import"),
                    help="a branch, or: command / forecast / dashboard / storefront / check / connections / shopify-auth / discover / venue / scout / edges / arbitrage / outcome / ears / pipeline / catalog / rebuy / orders / sync / suppliers / sell / po / brief / reprice / vendors / subs / ledger / act / customers / statement / count / audit / rank / channels / bundle / scan / license / host / tenant / autopilot / status / publish / add / describe / import")
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
    ap.add_argument("--run", action="store_true", help="subs: process every subscription that's due (raise buy POs / book sells)")
    ap.add_argument("--keygen", action="store_true", help="license: generate the owner keypair (run once)")
    ap.add_argument("--issue", metavar="CLIENT", help="license: mint a license token for a client (owner only)")
    ap.add_argument("--days", type=int, default=30, help="license: how many days the issued license is valid (default 30)")
    ap.add_argument("--every", type=int, default=60, help="autopilot: minutes between cycles (default 60)")
    ap.add_argument("--cycles", type=int, default=None, help="autopilot: stop after N cycles (default: run forever)")
    ap.add_argument("--reprice", action="store_true", help="autopilot: also reprice to the live market (needs Keepa + per-SKU asin)")
    ap.add_argument("--stock", action="store_true", help="publish: also push on-hand as tracked Shopify inventory (needs write_inventory)")
    # add: create/update one catalog product without a CSV
    ap.add_argument("--sku", help="add: the product SKU (required)")
    ap.add_argument("--name", help="add: product name")
    ap.add_argument("--cost", type=float, default=None, help="add: landed unit cost")
    ap.add_argument("--sell", type=float, default=None, help="add: sell price")
    ap.add_argument("--on-hand", type=int, default=None, dest="on_hand", help="add: units on hand")
    ap.add_argument("--monthly", type=int, default=None, help="add: monthly unit sales (demand)")
    ap.add_argument("--supplier", help="add: supplier name")
    ap.add_argument("--lead-time", type=int, default=None, dest="lead_time", help="add: supplier lead time (days)")
    ap.add_argument("--asin", help="add: Amazon ASIN (enables live repricing)")
    ap.add_argument("--description", help="add: product description (pushed to the channel listing)")
    ap.add_argument("--image", help="add: product image URL (pushed to the channel listing)")
    ap.add_argument("--update", action="store_true", help="publish: also update listings already on the channel (title/description/price/photo)")
    ap.add_argument("--overwrite", action="store_true", help="describe: rewrite descriptions even if a product already has one")
    ap.add_argument("--text", help="import: listings inline instead of --file (newline or blank-line separated)")
    args = ap.parse_args(argv)

    if args.max_calls is not None:
        from .adapters.base import Budget, set_budget
        set_budget(Budget(args.max_calls))      # 🪙 cap outbound API spend this run

    if args.branch == "license":
        return _license(args)
    if args.branch == "host":
        from . import host
        return host.serve(args)
    if args.branch == "tenant":
        return _tenant(args)
    # 🔒 the paywall: everything but licensing/hosting requires the owner key or a valid token
    from .license import require, LicenseError
    try:
        require()
    except LicenseError as e:
        raise SystemExit(str(e))

    if args.branch == "check":
        return _check()
    if args.branch == "connections":
        return _connections(args)
    if args.branch == "shopify-auth":
        return _shopify_auth(args)
    if args.branch == "outcome":
        return _outcome(args)
    if args.branch == "command":
        return _command(args)
    if args.branch == "forecast":
        return _forecast(args)
    if args.branch == "dashboard":
        from . import dashboard
        return dashboard.serve(args)
    if args.branch == "storefront":
        from . import storefront
        return storefront.serve(args)
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
    if args.branch == "vendors":
        return _vendors(args)
    if args.branch == "subs":
        return _subs(args)
    if args.branch == "ledger":
        return _ledger(args)
    if args.branch == "act":
        return _act(args)
    if args.branch == "customers":
        return _customers(args)
    if args.branch == "statement":
        return _statement(args)
    if args.branch == "count":
        return _count(args)
    if args.branch == "audit":
        return _audit(args)
    if args.branch == "rank":
        return _rank(args)
    if args.branch == "channels":
        return _channels(args)
    if args.branch == "bundle":
        return _bundle(args)
    if args.branch == "scan":
        return _scan(args)
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
    if args.branch == "autopilot":
        return _autopilot(args)
    if args.branch == "status":
        return _status(args)
    if args.branch == "add":
        return _add(args)
    if args.branch == "describe":
        return _describe(args)
    if args.branch == "import":
        return _import(args)
    if args.branch == "publish":
        from .adapters.base import AdapterError
        try:
            return _publish(args)
        except AdapterError as e:
            raise SystemExit("publish failed: %s\n(run `python -m ebe check`)" % e)
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
