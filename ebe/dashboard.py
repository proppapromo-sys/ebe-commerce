#!/usr/bin/env python3
"""
dashboard.py — EBE Command, a working web interface. Pure stdlib (http.server), zero deps.

  python -m ebe dashboard            # then open http://127.0.0.1:8765

Pages (top nav):
  • Today      — the daily action list, cash forecast, scout landscape, true edge
  • Live Edge  — type ASINs → live Keepa true-edge + buy-the-dip arbitrage
  • Supply·AI  — paste supplier listings → AI Ears normalize → cornerable shortlist
  • Venue      — enter POS counts → supplies consumed → reorder + cash

A profile switcher re-reads everything through any operator's lens; with --journal you can
mark ✓/✗ on edge rows and watch the Learning panel compound.
"""
from __future__ import annotations

import contextlib
import html
import io
import types
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

NAV = [("/", "Today", "today"), ("/live", "Live Edge", "live"),
       ("/supply", "Supply · AI", "supply"), ("/venue", "Venue", "venue")]

_CSS = """
:root{color-scheme:dark}
body{background:#0f1115;color:#e6e6e6;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0;padding:20px;max-width:1100px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;color:#9ad;margin:22px 0 8px;border-bottom:1px solid #243}
.sub{color:#89a;margin-bottom:8px}
.nav{margin:8px 0 12px}.nav a{display:inline-block;padding:5px 12px;margin-right:6px;border:1px solid #243;border-radius:8px;color:#bcd;text-decoration:none}
.nav a.navon{background:#1b2740;color:#fff;border-color:#356}
a{color:#9cf}
table{border-collapse:collapse;width:100%;margin:4px 0 8px}
td,th{padding:3px 10px;text-align:left;border-bottom:1px solid #1c2230}
th{color:#7fa;font-weight:600}.r{text-align:right}
.pill{padding:1px 7px;border-radius:8px;font-size:12px}
.CORNER{background:#163;color:#bfb}.STRONG{background:#136;color:#bdf}.TEST{background:#332;color:#dda}.pass{color:#667}
.warn{color:#f88}.ok{color:#8d8}.big{font-size:16px}
.card{background:#151823;border:1px solid #222a3a;border-radius:10px;padding:12px 16px;margin-bottom:10px}
input,textarea{background:#0c0e14;color:#e6e6e6;border:1px solid #2a3346;border-radius:7px;padding:6px 9px;font:inherit}
button{background:#1b2740;color:#fff;border:1px solid #356;border-radius:7px;padding:6px 14px;cursor:pointer;font:inherit}
textarea{width:100%;min-height:120px}
"""


def _esc(x):
    return html.escape(str(x))


def _parse_sales(text):
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = int(float(v.strip()))
            except ValueError:
                pass
    return out


# ── shared shell (nav + profile switcher) ────────────────────────────────────
def _shell(ctx, current, inner, refresh=False):
    cap = "" if ctx["capital"] is None else "&capital=%g" % ctx["capital"]
    nav = " ".join("<a class='%s' href='%s?profile=%s%s'>%s</a>"
                   % ("navon" if k == current else "", path, _esc(ctx["pkey"]), cap, _esc(label))
                   for path, label, k in NAV)
    cur_path = next((p for p, _, k in NAV if k == current), "/")
    profs = " · ".join("<a href='%s?profile=%s%s'>%s</a>" % (cur_path, _esc(p), cap, _esc(p)) for p in ctx["profiles"])
    head = ["<!doctype html><meta charset=utf-8><title>EBE Command</title>",
            "<meta name=viewport content='width=device-width,initial-scale=1'>"]
    if refresh:
        head.append("<meta http-equiv=refresh content=30>")
    head += ["<style>%s</style>" % _CSS, "<h1>EBE&nbsp;COMMAND</h1>",
             "<div class=nav>%s</div>" % nav,
             "<div class=sub>profile: %s · fees: %s · switch → %s</div>" % (_esc(ctx["pname"]), _esc(ctx["fee"]), profs)]
    return "".join(head) + inner


def _ctx_from_args(args):
    from .profile import PROFILES
    from .fees import PRESETS
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    return dict(pkey=args.profile or "generic", pname=prof.name, fee=PRESETS[args.fees].name,
                capital=getattr(args, "capital", None), profiles=sorted(PROFILES))


# ── TODAY page ───────────────────────────────────────────────────────────────
def _data(args):
    from .fees import PRESETS
    from .catalog.feeds import ListFeed, sample_live_catalog, sample_sourcing_catalog
    from .catalog.csv_io import load_products
    from .branches import sourcing, pricing, inventory, adspend, returns, scout
    from . import forecast
    from . import edges as edgemod
    from .profile import PROFILES

    fee = PRESETS[args.fees]
    prods = load_products(args.products) if args.products else None
    live = prods if prods is not None else sample_live_catalog()
    src = prods if prods is not None else sample_sourcing_catalog()
    if args.costs:
        from .costs import load_cost_sheet, apply_costs
        sheet = load_cost_sheet(args.costs)
        apply_costs(live, sheet); apply_costs(src, sheet)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        t_ret = returns.build(fee_model=fee).cycle()
        t_inv = inventory.build(live).cycle()
        t_pr = pricing.build(ListFeed(live), fee_model=fee).cycle()
        t_ad = adspend.build(fee_model=fee).cycle()
        t_src = sourcing.build(ListFeed(src), fee_model=fee).cycle()

    cal = forecast.cash_calendar(live)
    win = forecast.windows(cal)
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    market = scout.sample_market()

    learned, jstats = None, None
    journal_path = getattr(args, "journal", None)
    if journal_path:
        from .journal import Journal, category_trust
        recs = Journal(journal_path).read()
        learned = category_trust(recs)
        jstats = {"decisions": sum(1 for r in recs if r.get("kind") == "decision"),
                  "outcomes": sum(1 for r in recs if r.get("kind") == "outcome"), "trust": learned}

    ranked = edgemod.rank(market, prof, fee, learned=learned)
    land = scout.landscape(market, prof, fee)
    from .venue.sample import sample_menu, sample_consumables, sample_sales
    venue_cal = forecast.venue_calendar(sample_sales(), sample_menu(), sample_consumables())
    return dict(fee=fee, prof=prof, capital=args.capital, pkey=args.profile or "generic",
                ret=t_ret, inv=t_inv, pr=t_pr, ad=t_ad, src=t_src, cal=cal, win=win,
                ed=ranked, land=land, venue=venue_cal, profiles=sorted(PROFILES),
                journal=journal_path, jstats=jstats)


def _today_inner(d):
    out = ["<h2>🎯 Today</h2>"]
    leak = sum(s for _, s in d["ret"])
    if d["ret"]:
        out.append("<div class=card><b class=warn>🩹 Stop the leak</b><table><tr><th>SKU<th class=r>returns<th class=r>$/mo</tr>")
        for it, s in d["ret"]:
            out.append("<tr><td>%s<td class=r>%.0f%%<td class=r>$%.0f</tr>" % (_esc(it["name"]), it.get("_rate", 0) * 100, s))
        out.append("</table></div>")
    rcash = sum(int(s) * it.get("cost", 0) for it, s in d["inv"])
    if d["inv"]:
        out.append("<div class=card><b>🚚 Reorder</b><table><tr><th>SKU<th class=r>units<th class=r>cash</tr>")
        for it, s in d["inv"]:
            out.append("<tr><td>%s<td class=r>%d<td class=r>$%.0f</tr>" % (_esc(it["name"]), int(s), int(s) * it.get("cost", 0)))
        out.append("</table></div>")
    uplift = sum(s for _, s in d["pr"])
    if d["pr"]:
        out.append("<div class=card><b>🏷️ Reprice</b><table><tr><th>SKU<th class=r>now<th class=r>→<th class=r>+$/mo</tr>")
        for it, s in d["pr"]:
            out.append("<tr><td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>+$%.0f</tr>" % (_esc(it["name"]), it["sell"], it.get("_best_price", it["sell"]), s))
        out.append("</table></div>")
    if d["ad"]:
        out.append("<div class=card><b>📈 Scale ads</b><table><tr><th>campaign<th class=r>+$/mo</tr>")
        for it, s in d["ad"]:
            out.append("<tr><td>%s<td class=r>+$%.0f</tr>" % (_esc(it["name"]), s))
        out.append("</table></div>")
    scash = sum(s for _, s in d["src"])
    if d["src"]:
        out.append("<div class=card><b>📦 Source (test batch)</b><table><tr><th>product<th class=r>$ batch</tr>")
        for it, s in d["src"]:
            out.append("<tr><td>%s<td class=r>$%.0f</tr>" % (_esc(it["name"]), s))
        out.append("</table></div>")
    n = len(d["ret"]) + len(d["inv"]) + len(d["pr"]) + len(d["ad"]) + len(d["src"])
    cash_out = rcash + scash
    summ = "<div class=card><span class=big>%d actions today</span> · cash out ≈ $%.0f · monthly upside ≈ $%.0f" % (n, cash_out, uplift + leak)
    if d["capital"] is not None:
        diff = d["capital"] - cash_out
        summ += " · vs $%.0f → %s" % (d["capital"], "<span class=ok>headroom $%.0f</span>" % diff if diff >= 0 else "<span class=warn>SHORT $%.0f</span>" % (-diff))
    out.append(summ + "</div>")

    w = d["win"]
    out.append("<h2>💵 Cash forecast</h2><div class=card>next 7d: <b>$%.0f</b> · 30d: <b>$%.0f</b> · 60d: <b>$%.0f</b> · 90d: <b>$%.0f</b></div>" % (w[7], w[30], w[60], w[90]))
    if d["cal"]:
        out.append("<table><tr><th>when<th>item<th class=r>reorder<th class=r>cash<th class=r>cover</tr>")
        for r in d["cal"]:
            when = "NOW" if r["days_until"] <= 0 else "in %.0fd" % r["days_until"]
            out.append("<tr><td>%s<td>%s<td class=r>%d<td class=r>$%.0f<td class=r>%.0fd</tr>" % (when, _esc(r["name"]), r["qty"], r["cash"], r["cover"]))
        out.append("</table>")

    jr = d.get("journal")
    out.append("<h2>🧭 True edge (scout)%s</h2>" % (" · 🔁 learned" if d.get("jstats") and d["jstats"]["trust"] else ""))
    out.append("<table><tr><th>product<th class=r>EDGE<th class=r>moat<th>verdict%s</tr>" % ("<th>mark" if jr else ""))
    for e in d["ed"]:
        mark = ""
        if jr:
            iid = urllib.parse.quote(str(e.item.get("id", ""))); cat = urllib.parse.quote(str(e.item.get("category", "")))
            mark = "<td><a href='/record?id=%s&cat=%s&score=1'>✓ win</a> <a href='/record?id=%s&cat=%s&score=-1'>✗ loss</a>" % (iid, cat, iid, cat)
        out.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f%%<td><span class='pill %s'>%s</span>%s</tr>" % (_esc(e.item["name"]), e.composite * 100, e.moat * 100, e.verdict, e.verdict, mark))
    out.append("</table>")

    out.append("<h2>🗺️ Landscape</h2><table><tr><th>category<th class=r>crowding<th class=r>demand<th class=r>ROI<th class=r>your-edge<th>read</tr>")
    for r in d.get("land", []):
        read = "leaders dominate" if r["competition"] >= 0.75 else ("OPEN LANE" if r["competition"] <= 0.40 else "contested")
        fit = "+%.0f%%" % (r["fit"] * 100) if r["fit"] else "–"
        out.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f/mo<td class=r>%.0f%%<td class=r>%s<td>%s</tr>" % (_esc(r["category"]), r["competition"] * 100, r["demand"], r["roi"] * 100, fit, read))
    out.append("</table>")

    if d.get("jstats"):
        js = d["jstats"]
        out.append("<h2>🔁 Learning</h2><div class=card>%d decision(s) · %d outcome(s) → %s</div>" % (js["decisions"], js["outcomes"], _esc(jr)))
        if js["trust"]:
            out.append("<table><tr><th>category<th class=r>proven trust</tr>")
            for c, t in sorted(js["trust"].items(), key=lambda kv: -kv[1]):
                cls = "ok" if t >= 0.55 else ("warn" if t < 0.45 else "")
                out.append("<tr><td>%s<td class=r><span class=%s>%.0f%%</span></tr>" % (_esc(c), cls, t * 100))
            out.append("</table>")
        else:
            out.append("<div class=sub>mark a few ✓/✗ above, then refresh — proven categories will rise.</div>")
    return "".join(out)


def render(d):
    ctx = dict(pkey=d.get("pkey", "generic"), pname=d["prof"].name, fee=d["fee"].name,
               capital=d["capital"], profiles=d.get("profiles", []))
    return _shell(ctx, "today", _today_inner(d), refresh=True)


# ── LIVE EDGE page (Keepa) ───────────────────────────────────────────────────
def render_live(args, asins):
    inner = ["<h2>🧭 Live edge &amp; arbitrage (Keepa)</h2>",
             "<form class=card action='/live' method=get>"
             "ASINs: <input name=asins value='%s' size=48 placeholder='B08VRZTHDL,B0BTD83JZR'> "
             "<input type=hidden name=profile value='%s'> <button>Score live</button></form>"
             % (_esc(asins or ""), _esc(args.profile or "generic"))]
    if asins:
        ids = [a.strip() for a in asins.split(",") if a.strip()]
        try:
            from .adapters.keepa import KeepaClient, live_edge_item, keepa_price_points
            from . import edges as edgemod, arbitrage as arb
            from .profile import PROFILES
            from .fees import PRESETS
            client = KeepaClient()
            fee = PRESETS[args.fees]
            prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
            kps = client.fetch(ids)
            ranked = edgemod.rank([live_edge_item(kp, 0.35) for kp in kps], prof, fee)
            inner.append("<table><tr><th>product<th class=r>EDGE<th class=r>moat<th>verdict</tr>")
            for e in ranked:
                inner.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f%%<td><span class='pill %s'>%s</span></tr>" % (_esc(e.item["name"]), e.composite * 100, e.moat * 100, e.verdict, e.verdict))
            inner.append("</table><h2>💱 Buy-the-dip</h2><table><tr><th>product<th class=r>now<th class=r>avg<th class=r>dip<th>signal</tr>")
            for kp in kps:
                s = arb.signal(keepa_price_points(kp))
                if s:
                    inner.append("<tr><td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>%.0f%%<td>%s</tr>" % (_esc((kp.get("title") or kp.get("asin") or "")[:34]), s.current, s.avg or 0, s.dip * 100, s.verdict))
            inner.append("</table>")
        except Exception as ex:
            inner.append("<div class='card warn'>live data error: %s</div>" % _esc(str(ex)))
    return _shell(_ctx_from_args(args), "live", "".join(inner))


# ── SUPPLY · AI page (Ears + pipeline) ───────────────────────────────────────
def render_supply(args, listings):
    inner = ["<h2>👂 Supply intake → cornerable shortlist (AI)</h2>",
             "<form class=card action='/supply' method=get>"
             "<div class=sub>paste supplier listings, one per line:</div>"
             "<textarea name=listings placeholder='Disposable hookah tips 1000pcs/box $30 MOQ 10'>%s</textarea>"
             "<input type=hidden name=profile value='%s'><br><button>Run pipeline</button></form>"
             % (_esc(listings or ""), _esc(args.profile or "generic"))]
    if listings and listings.strip():
        lines = [ln.strip() for ln in listings.splitlines() if ln.strip()]
        try:
            from .ai.ears import normalize_listings
            from . import edges as edgemod
            from .profile import PROFILES
            from .fees import PRESETS
            prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
            fee = PRESETS[args.fees]
            prods = normalize_listings(lines)
            ranked = edgemod.rank([p.as_item() for p in prods], prof, fee)
            inner.append("<table><tr><th>product<th>category<th class=r>cost<th class=r>sell<th class=r>EDGE<th>verdict</tr>")
            for e in ranked:
                it = e.item
                inner.append("<tr><td>%s<td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>%.0f%%<td><span class='pill %s'>%s</span></tr>" % (_esc(it.get("name", "?")), _esc(it.get("category", "?")), it.get("cost", 0), it.get("sell", 0), e.composite * 100, e.verdict, e.verdict))
            inner.append("</table><div class=sub>get real sell/demand (Live Edge tab) for the top ones, then confirm ROI.</div>")
        except Exception as ex:
            inner.append("<div class='card warn'>AI error: %s</div>" % _esc(str(ex)))
    return _shell(_ctx_from_args(args), "supply", "".join(inner))


# ── VENUE page ───────────────────────────────────────────────────────────────
def render_venue(args, sales_str):
    from .venue.sample import sample_menu, sample_consumables, sample_sales
    from .venue.bom import explode_usage
    from . import forecast
    menu, cons = sample_menu(), sample_consumables()
    sales = _parse_sales(sales_str) if sales_str else sample_sales()
    usage = explode_usage(sales, menu)
    cal = forecast.venue_calendar(sales, menu, cons)
    default = sales_str or ",".join("%s=%d" % (k, v) for k, v in sales.items())
    inner = ["<h2>🏪 Venue supplies</h2>",
             "<form class=card action='/venue' method=get>POS counts: "
             "<input name=sales value='%s' size=40 placeholder='drink=500,hookah=120,takeout=85'> "
             "<input type=hidden name=profile value='%s'><button>Run</button></form>"
             % (_esc(default), _esc(args.profile or "generic"))]
    inner.append("<table><tr><th>consumable<th class=r>used (period)</tr>")
    for cid, used in sorted(usage.items(), key=lambda kv: -kv[1]):
        nm = cons[cid].name if cid in cons else cid
        inner.append("<tr><td>%s<td class=r>%.0f</tr>" % (_esc(nm), used))
    inner.append("</table>")
    if cal:
        inner.append("<h2>🛒 Reorder horizon</h2><table><tr><th>when<th>item<th class=r>reorder<th class=r>cash<th class=r>cover</tr>")
        for r in cal:
            when = "NOW" if r["days_until"] <= 0 else "in %.0fd" % r["days_until"]
            inner.append("<tr><td>%s<td>%s<td class=r>%d<td class=r>$%.0f<td class=r>%.0fd</tr>" % (when, _esc(r["name"]), r["qty"], r["cash"], r["cover"]))
        inner.append("</table>")
    return _shell(_ctx_from_args(args), "venue", "".join(inner))


def _req_args(base, query):
    from .fees import PRESETS
    a = types.SimpleNamespace(**vars(base))
    qs = urllib.parse.parse_qs(query)
    if qs.get("profile"):
        a.profile = qs["profile"][0]
    if qs.get("fees") and qs["fees"][0] in PRESETS:
        a.fees = qs["fees"][0]
    if qs.get("capital"):
        try:
            a.capital = float(qs["capital"][0])
        except ValueError:
            pass
    return a


def serve(args):
    port = getattr(args, "port", None) or 8765

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            if path == "/record":
                jr = getattr(args, "journal", None)
                if jr and qs.get("id"):
                    from .journal import Journal
                    try:
                        sc = float(qs.get("score", ["1"])[0])
                    except ValueError:
                        sc = 1.0
                    Journal(jr).record_outcome("edges", qs["id"][0], sc, category=(qs.get("cat") or [None])[0])
                self.send_response(303); self.send_header("Location", "/"); self.end_headers(); return
            a = _req_args(args, query)
            try:
                if path in ("/", ""):
                    body = render(_data(a))
                elif path == "/live":
                    body = render_live(a, (qs.get("asins") or [""])[0])
                elif path == "/supply":
                    body = render_supply(a, (qs.get("listings") or [""])[0])
                elif path == "/venue":
                    body = render_venue(a, (qs.get("sales") or [""])[0])
                else:
                    self.send_response(404); self.end_headers(); return
                body = body.encode("utf-8")
            except Exception as ex:
                body = ("<pre>error: %s</pre>" % html.escape(str(ex))).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", port), Handler)
    print("EBE COMMAND dashboard → http://127.0.0.1:%d   (Ctrl+C to stop)" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        print("\nstopped.")
