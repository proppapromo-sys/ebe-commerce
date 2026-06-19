#!/usr/bin/env python3
"""
dashboard.py — EBE Command in a browser. Pure stdlib (http.server) — zero dependencies.

  python -m ebe dashboard            # then open http://127.0.0.1:8765

Serves the daily action list (command), the cash forecast (with runway), and the true-edge
table on one page. Every refresh recomputes live, so it doubles as a control screen.
"""
from __future__ import annotations

import contextlib
import html
import io
import types
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer


def _data(args):
    """Compute everything the page shows (branch tickets suppressed to a throwaway buffer)."""
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
    ranked = edgemod.rank(market, prof, fee)
    land = scout.landscape(market, prof, fee)
    from .venue.sample import sample_menu, sample_consumables, sample_sales
    venue_cal = forecast.venue_calendar(sample_sales(), sample_menu(), sample_consumables())
    return dict(fee=fee, prof=prof, capital=args.capital,
                ret=t_ret, inv=t_inv, pr=t_pr, ad=t_ad, src=t_src,
                cal=cal, win=win, ed=ranked, land=land, venue=venue_cal,
                profiles=sorted(PROFILES))


_CSS = """
:root{color-scheme:dark}
body{background:#0f1115;color:#e6e6e6;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace;margin:0;padding:24px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;color:#9ad;margin:24px 0 8px;border-bottom:1px solid #243}
.sub{color:#89a;margin-bottom:8px}
table{border-collapse:collapse;width:100%;margin:4px 0 8px}
td,th{padding:3px 10px;text-align:left;border-bottom:1px solid #1c2230}
th{color:#7fa;font-weight:600}
.r{text-align:right}
.pill{padding:1px 7px;border-radius:8px;font-size:12px}
.CORNER{background:#163;color:#bfb}.STRONG{background:#136;color:#bdf}.TEST{background:#332;color:#dda}.pass{color:#667}
.warn{color:#f88}.ok{color:#8d8}.big{font-size:16px}
.card{background:#151823;border:1px solid #222a3a;border-radius:10px;padding:12px 16px;margin-bottom:10px}
"""


def _esc(x):
    return html.escape(str(x))


def render(d):
    fee, prof = d["fee"], d["prof"]
    out = ["<!doctype html><meta charset=utf-8><title>EBE Command</title>",
           "<meta name=viewport content='width=device-width,initial-scale=1'>",
           "<meta http-equiv=refresh content=30>",          # live control screen
           "<style>%s</style>" % _CSS,
           "<h1>EBE&nbsp;COMMAND</h1>",
           "<div class=sub>profile: %s · fees: %s · auto-refresh 30s</div>" % (_esc(prof.name), _esc(fee.name))]
    # profile switcher
    cap = "" if d["capital"] is None else "&capital=%g" % d["capital"]
    nav = " · ".join("<a href='/?profile=%s%s'>%s</a>" % (_esc(p), cap, _esc(p)) for p in d.get("profiles", []))
    out.append("<div class=sub>profile → %s</div>" % nav)

    # ── TODAY ──
    out.append("<h2>🎯 Today</h2>")
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
            out.append("<tr><td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>+$%.0f</tr>"
                       % (_esc(it["name"]), it["sell"], it.get("_best_price", it["sell"]), s))
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
        summ += " · vs $%.0f capital → %s" % (d["capital"],
                "<span class=ok>headroom $%.0f</span>" % diff if diff >= 0 else "<span class=warn>SHORT $%.0f</span>" % (-diff))
    out.append(summ + "</div>")

    # ── FORECAST ──
    w = d["win"]
    out.append("<h2>💵 Cash forecast</h2>")
    out.append("<div class=card>next 7d: <b>$%.0f</b> · 30d: <b>$%.0f</b> · 60d: <b>$%.0f</b> · 90d: <b>$%.0f</b></div>" % (w[7], w[30], w[60], w[90]))
    if d["cal"]:
        out.append("<table><tr><th>when<th>item<th class=r>reorder<th class=r>cash<th class=r>cover</tr>")
        for r in d["cal"]:
            when = "NOW" if r["days_until"] <= 0 else "in %.0fd" % r["days_until"]
            out.append("<tr><td>%s<td>%s<td class=r>%d<td class=r>$%.0f<td class=r>%.0fd</tr>"
                       % (when, _esc(r["name"]), r["qty"], r["cash"], r["cover"]))
        out.append("</table>")

    # ── TRUE EDGE ──
    out.append("<h2>🧭 True edge (scout)</h2>")
    out.append("<table><tr><th>product<th class=r>EDGE<th class=r>moat<th>verdict</tr>")
    for e in d["ed"]:
        out.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f%%<td><span class='pill %s'>%s</span></tr>"
                   % (_esc(e.item["name"]), e.composite * 100, e.moat * 100, e.verdict, e.verdict))
    out.append("</table>")

    # ── LANDSCAPE ──
    out.append("<h2>🗺️ Landscape</h2>")
    out.append("<table><tr><th>category<th class=r>crowding<th class=r>demand<th class=r>ROI<th class=r>your-edge<th>read</tr>")
    for r in d.get("land", []):
        read = "leaders dominate" if r["competition"] >= 0.75 else ("OPEN LANE" if r["competition"] <= 0.40 else "contested")
        fit = "+%.0f%%" % (r["fit"] * 100) if r["fit"] else "–"
        out.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f/mo<td class=r>%.0f%%<td class=r>%s<td>%s</tr>"
                   % (_esc(r["category"]), r["competition"] * 100, r["demand"], r["roi"] * 100, fit, read))
    out.append("</table>")

    # ── VENUE SUPPLIES ──
    if d.get("venue"):
        out.append("<h2>🏪 Venue supplies</h2><table><tr><th>when<th>item<th class=r>reorder<th class=r>cash<th class=r>cover</tr>")
        for r in d["venue"]:
            when = "NOW" if r["days_until"] <= 0 else "in %.0fd" % r["days_until"]
            out.append("<tr><td>%s<td>%s<td class=r>%d<td class=r>$%.0f<td class=r>%.0fd</tr>"
                       % (when, _esc(r["name"]), r["qty"], r["cash"], r["cover"]))
        out.append("</table>")
    return "".join(out)


def _req_args(base, query):
    """Per-request args: clone base, override profile/fees/capital from the query string."""
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
            if path not in ("/", ""):
                self.send_response(404); self.end_headers(); return
            try:
                body = render(_data(_req_args(args, query))).encode("utf-8")
            except Exception as ex:
                body = ("<pre>dashboard error: %s</pre>" % html.escape(str(ex))).encode("utf-8")
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
