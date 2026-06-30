#!/usr/bin/env python3
"""
dashboard.py — EBE Command, a working web interface with an EBE Orb-style HUD.
Pure stdlib (http.server), zero deps; all motion is CSS + a few lines of vanilla JS.

  python -m ebe dashboard            # then open http://127.0.0.1:8765

Pages (top nav):
  • Today      — the daily action list, cash forecast, scout landscape, true edge
  • Re-buy     — proposed purchase orders from the live database; approve/receive in-browser
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

# Generalized e-commerce nav (any seller, not a venue). Venue/Supply routes still exist
# but are off the default nav — they were niche + carried personal sample data.
NAV = [("/", "Today", "today"), ("/catalog", "Catalog", "catalog"), ("/rebuy", "Restock", "rebuy"),
       ("/reprice", "Pricing", "reprice"), ("/pnl", "Profit", "pnl"), ("/source", "Sourcing", "source"),
       ("/live", "Market", "live"), ("/act", "Actions", "act"), ("/brief", "Brief", "brief"),
       ("/report", "Orb Report", "report"), ("/membership", "Member", "membership")]

_CSS = """
:root{
  color-scheme:dark;
  --bg:#060a12; --bg2:#0a1322;
  --panel:rgba(17,28,46,.55); --brd:rgba(86,180,255,.18);
  --cyan:#39e6ff; --cyandim:#88d6ec; --green:#38ffb0; --amber:#ffc24b; --red:#ff7a7a;
  --ink:#d6e8ff; --mut:#7e93b0;
  --hud:"SFMono-Regular",ui-monospace,Menlo,Consolas,monospace;
  --sans:ui-sans-serif,system-ui,"Segoe UI",Roboto,Helvetica,sans-serif;
}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;color:var(--ink);font:14px/1.55 var(--sans);overflow-x:hidden;
  padding:0 0 70px;
  background:
    radial-gradient(1200px 720px at 82% -12%, rgba(33,96,176,.28), transparent 60%),
    radial-gradient(900px 620px at -12% 112%, rgba(18,128,150,.18), transparent 55%),
    linear-gradient(180deg,var(--bg),var(--bg2));
  background-attachment:fixed;}
body::before{content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:
    linear-gradient(rgba(70,150,210,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(70,150,210,.05) 1px,transparent 1px);
  background-size:44px 44px;
  -webkit-mask:radial-gradient(circle at 50% 26%,#000,transparent 92%);
          mask:radial-gradient(circle at 50% 26%,#000,transparent 92%);
  animation:gridpan 26s linear infinite;}
@keyframes gridpan{to{background-position:44px 44px}}
.sweep{position:fixed;top:0;left:0;right:0;height:2px;z-index:40;opacity:.9;pointer-events:none;
  background:linear-gradient(90deg,transparent,var(--cyan),transparent);
  animation:sweep 2.2s cubic-bezier(.4,0,.2,1) both;}
@keyframes sweep{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

.topbar{position:sticky;top:0;z-index:6;display:flex;justify-content:space-between;align-items:center;
  gap:16px;flex-wrap:wrap;padding:13px 26px;
  background:linear-gradient(180deg,rgba(7,12,22,.94),rgba(7,12,22,.55));
  -webkit-backdrop-filter:blur(13px);backdrop-filter:blur(13px);border-bottom:1px solid var(--brd);}
.brand{display:flex;align-items:center;gap:13px;font:700 18px/1 var(--hud);letter-spacing:.16em;
  color:#eaf8ff;text-shadow:0 0 20px rgba(57,230,255,.4)}
.orb{position:relative;display:inline-block;width:19px;height:19px;flex:0 0 auto}
.orb i{position:absolute;border-radius:50%;inset:0;pointer-events:none}
.orb .orb-core{inset:3px;background:radial-gradient(circle at 32% 28%,#f2ffff,#7df0ff 38%,#39e6ff 62%,#0a6e8f);
  box-shadow:0 0 9px var(--cyan),0 0 20px rgba(57,230,255,.8),inset 0 0 5px rgba(255,255,255,.6);
  animation:pulse 2.4s ease-in-out infinite}
.orb .orb-aura{inset:-9px;background:radial-gradient(circle,rgba(57,230,255,.5),rgba(57,230,255,.12) 45%,transparent 70%);
  filter:blur(2.5px);animation:breathe 3.4s ease-in-out infinite}
.orb .orb-ring{inset:-4px;border:1.5px solid rgba(125,240,255,.65);
  border-top-color:transparent;border-bottom-color:transparent;
  box-shadow:0 0 8px -1px rgba(57,230,255,.5);animation:orbit 2.6s linear infinite}
.orb .orb-ring2{inset:-9px;border:1px solid rgba(57,230,255,.28);
  border-left-color:transparent;border-right-color:transparent;animation:orbit 5.4s linear infinite reverse}
.orb .orb-sat{inset:-4px;animation:orbit 2.6s linear infinite}
.orb .orb-sat::before{content:'';position:absolute;top:-2px;left:50%;width:3.5px;height:3.5px;margin-left:-1.75px;
  border-radius:50%;background:#f2ffff;box-shadow:0 0 7px 1.5px var(--cyan),0 0 12px rgba(57,230,255,.7)}
.brand:hover .orb-ring{animation-duration:1.1s}
.brand:hover .orb-sat{animation-duration:1.1s}
.brand:hover .orb-core{box-shadow:0 0 14px var(--cyan),0 0 34px rgba(57,230,255,1),inset 0 0 6px rgba(255,255,255,.8)}
.brand .orbname{color:var(--cyan);opacity:.85;font-size:12px;letter-spacing:.22em;margin-left:2px}
@keyframes pulse{0%,100%{transform:scale(1);opacity:.94}50%{transform:scale(1.14);opacity:1}}
@keyframes breathe{0%,100%{transform:scale(.88);opacity:.5}50%{transform:scale(1.18);opacity:.95}}
@keyframes orbit{to{transform:rotate(360deg)}}
.status{display:flex;align-items:center;gap:9px;font:600 11px/1 var(--hud);letter-spacing:.12em;
  text-transform:uppercase;color:var(--mut)}
.status .sep{opacity:.4}
.status .dot{width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 10px var(--green);animation:pulse 2s infinite}
#clock{color:var(--cyandim)}

.nav{display:flex;flex-wrap:wrap;gap:8px;max-width:1160px;margin:16px auto 4px;padding:0 26px;position:relative;z-index:3}
.nav a{font:600 12px/1 var(--hud);letter-spacing:.09em;text-transform:uppercase;text-decoration:none;
  color:var(--cyandim);padding:10px 17px;border:1px solid var(--brd);border-radius:11px;
  background:rgba(20,32,52,.4);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  transition:.28s cubic-bezier(.2,.8,.2,1)}
.nav a:hover{color:#eaffff;border-color:var(--cyan);transform:translateY(-2px);
  box-shadow:0 0 0 1px rgba(57,230,255,.3),0 10px 26px -10px rgba(57,230,255,.6)}
.nav a.navon{color:#00121a;background:linear-gradient(180deg,#86f0ff,#39e6ff);border-color:#86f0ff;
  box-shadow:0 0 24px -4px var(--cyan)}

.wrap{max-width:1160px;margin:0 auto;padding:0 26px;position:relative;z-index:2}
.switchline{margin:6px auto 10px;color:var(--mut);font-size:12px;letter-spacing:.04em}
.switchline a{color:var(--cyandim);text-decoration:none}.switchline a:hover{color:var(--cyan)}

h2{font:600 13px/1.2 var(--hud);letter-spacing:.15em;text-transform:uppercase;color:#c4ecff;
  margin:28px 0 13px;display:flex;align-items:center;gap:11px;animation:rise .5s both}
h2::before{content:"";width:3px;height:15px;border-radius:2px;
  background:linear-gradient(var(--cyan),transparent);box-shadow:0 0 10px var(--cyan)}

.card{position:relative;background:var(--panel);border:1px solid var(--brd);border-radius:15px;
  padding:15px 19px;margin:0 0 14px;-webkit-backdrop-filter:blur(11px);backdrop-filter:blur(11px);
  box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 22px 44px -30px rgba(0,0,0,.95);
  transition:.3s cubic-bezier(.2,.8,.2,1);animation:rise .5s both}
.card::before,.card::after{content:"";position:absolute;width:15px;height:15px;
  border:1px solid var(--cyan);opacity:.45;transition:.3s}
.card::before{top:-1px;left:-1px;border-right:0;border-bottom:0;border-radius:15px 0 0 0}
.card::after{bottom:-1px;right:-1px;border-left:0;border-top:0;border-radius:0 0 15px 0}
.card:hover{border-color:rgba(57,230,255,.4);transform:translateY(-2px);
  box-shadow:0 0 0 1px rgba(57,230,255,.15),0 28px 56px -32px rgba(57,230,255,.55)}
.card:hover::before,.card:hover::after{opacity:.9;width:20px;height:20px}
@keyframes rise{from{opacity:0;transform:translateY(15px)}to{opacity:1;transform:none}}
.wrap>*:nth-child(1){animation-delay:.02s}.wrap>*:nth-child(2){animation-delay:.06s}
.wrap>*:nth-child(3){animation-delay:.10s}.wrap>*:nth-child(4){animation-delay:.14s}
.wrap>*:nth-child(5){animation-delay:.18s}.wrap>*:nth-child(6){animation-delay:.22s}
.wrap>*:nth-child(7){animation-delay:.26s}.wrap>*:nth-child(8){animation-delay:.30s}
.wrap>*:nth-child(9){animation-delay:.34s}.wrap>*:nth-child(n+10){animation-delay:.38s}

table{border-collapse:separate;border-spacing:0;width:100%;margin:6px 0 12px;font:13px/1.5 var(--hud);
  background:rgba(9,16,30,.42);border:1px solid var(--brd);border-radius:13px;overflow:hidden;animation:rise .5s both}
th{font:600 11px/1 var(--hud);letter-spacing:.1em;text-transform:uppercase;color:var(--cyandim);
  text-align:left;padding:11px 13px;background:rgba(21,35,58,.6);border-bottom:1px solid var(--brd)}
td{padding:10px 13px;border-bottom:1px solid rgba(70,100,140,.12)}
tr:last-child td{border-bottom:0}
tbody tr,table tr{transition:.18s}
tr:hover td{background:rgba(57,230,255,.06)}
.r{text-align:right;font-variant-numeric:tabular-nums}

.pill{display:inline-block;padding:3px 11px;border-radius:20px;font:600 11px/1 var(--hud);letter-spacing:.06em}
.CORNER{background:rgba(56,255,176,.14);color:#7dffce;box-shadow:0 0 0 1px rgba(56,255,176,.35),0 0 15px -2px rgba(56,255,176,.5)}
.STRONG{background:rgba(59,160,255,.14);color:#9cd4ff;box-shadow:0 0 0 1px rgba(59,160,255,.35)}
.TEST{background:rgba(255,194,75,.14);color:#ffd98a;box-shadow:0 0 0 1px rgba(255,194,75,.3)}
.pass{color:var(--mut)}
.warn{color:var(--amber)}.ok{color:var(--green)}
.big{font:700 22px/1 var(--hud);color:#eaffff;text-shadow:0 0 18px rgba(57,230,255,.4)}
.sub{color:var(--mut);font-size:12px;letter-spacing:.03em}

.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:8px 0 16px}
.metric{position:relative;background:var(--panel);border:1px solid var(--brd);border-radius:15px;
  padding:15px 17px;-webkit-backdrop-filter:blur(11px);backdrop-filter:blur(11px);animation:rise .5s both;overflow:hidden}
.metric::after{content:"";position:absolute;inset:0;background:linear-gradient(120deg,transparent 40%,rgba(57,230,255,.07),transparent 60%);
  transform:translateX(-100%);animation:shine 5s ease-in-out infinite}
@keyframes shine{0%,60%{transform:translateX(-100%)}80%,100%{transform:translateX(100%)}}
.metric .k{font:600 10px/1 var(--hud);letter-spacing:.15em;text-transform:uppercase;color:var(--mut)}
.metric .v{font:700 27px/1.1 var(--hud);color:#eaffff;margin-top:9px;text-shadow:0 0 16px rgba(57,230,255,.35)}
.metric.alert .v{color:#ffd98a;text-shadow:0 0 16px rgba(255,194,75,.4)}
.metric.go .v{color:#7dffce;text-shadow:0 0 16px rgba(56,255,176,.4)}

input,textarea,select{background:rgba(7,13,24,.7);color:var(--ink);border:1px solid var(--brd);
  border-radius:10px;padding:9px 12px;font:13px var(--hud);transition:.2s}
input:focus,textarea:focus{outline:none;border-color:var(--cyan);box-shadow:0 0 0 3px rgba(57,230,255,.15)}
textarea{width:100%;min-height:120px}
button,.btn{position:relative;overflow:hidden;cursor:pointer;text-decoration:none;display:inline-block;
  font:600 12px/1 var(--hud);letter-spacing:.06em;text-transform:uppercase;color:#00121a;
  background:linear-gradient(180deg,#86f0ff,#39e6ff);border:0;border-radius:10px;padding:10px 16px;
  box-shadow:0 8px 22px -8px var(--cyan);transition:.2s cubic-bezier(.2,.8,.2,1)}
button:hover,.btn:hover{transform:translateY(-2px);box-shadow:0 13px 30px -8px var(--cyan)}
button:active,.btn:active{transform:translateY(0)}
.btn.ghost{color:var(--cyandim);background:transparent;border:1px solid var(--brd);box-shadow:none}
.btn.ghost:hover{color:#eaffff;border-color:var(--cyan);box-shadow:0 0 0 1px rgba(57,230,255,.3)}
.btn.go{background:linear-gradient(180deg,#7dffce,#38ffb0)}
.btn.warn{background:linear-gradient(180deg,#ffd98a,#ffc24b)}
.btn.sm{padding:6px 11px;font-size:11px;border-radius:8px}
.rip{position:absolute;width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.55);
  transform:translate(-50%,-50%);animation:rip .6s ease-out forwards;pointer-events:none}
@keyframes rip{to{width:260px;height:260px;opacity:0}}
.banner{border-radius:12px;padding:11px 15px;margin:0 0 14px;font-size:13px;
  background:rgba(255,194,75,.08);border:1px solid rgba(255,194,75,.3);color:#ffd98a;animation:rise .5s both}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

_JS = """<script>
(function(){
function p(n){return(n<10?'0':'')+n;}
function tick(){var c=document.getElementById('clock');if(!c)return;var d=new Date();
c.textContent=p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());}
tick();setInterval(tick,1000);
document.querySelectorAll('[data-count]').forEach(function(el){
var to=parseFloat(el.getAttribute('data-count'))||0,pre=el.getAttribute('data-pre')||'',
suf=el.getAttribute('data-suf')||'',s=null,dur=900;
function f(t){if(!s)s=t;var q=Math.min(1,(t-s)/dur),e=1-Math.pow(1-q,3);
el.textContent=pre+Math.round(to*e).toLocaleString()+suf;if(q<1)requestAnimationFrame(f);}
requestAnimationFrame(f);});
document.addEventListener('click',function(ev){var b=ev.target.closest('button,.btn');if(!b)return;
var r=document.createElement('span');r.className='rip';var q=b.getBoundingClientRect();
r.style.left=(ev.clientX-q.left)+'px';r.style.top=(ev.clientY-q.top)+'px';b.appendChild(r);
setTimeout(function(){if(r.parentNode)r.parentNode.removeChild(r);},600);});
})();
</script>"""


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


# ── shared HUD shell (top bar + nav + profile switcher) ──────────────────────
def _shell(ctx, current, inner, refresh=False):
    cap = "" if ctx["capital"] is None else "&capital=%g" % ctx["capital"]
    nav = "".join("<a class='%s' href='%s?profile=%s%s'>%s</a>"
                  % ("navon" if k == current else "", path, _esc(ctx["pkey"]), cap, _esc(label))
                  for path, label, k in NAV)
    cur_path = next((p for p, _, k in NAV if k == current), "/")
    profs = " · ".join("<a href='%s?profile=%s%s'>%s</a>" % (cur_path, _esc(p), cap, _esc(p))
                       for p in ctx["profiles"])
    from . import brand
    bname = _esc(brand.upper()).replace(" ", "&nbsp;")
    head = ["<!doctype html><html lang=en><head><meta charset=utf-8><title>%s</title>" % _esc(brand.name()),
            "<meta name=viewport content='width=device-width,initial-scale=1'>"]
    if refresh:
        head.append("<meta http-equiv=refresh content=45>")
    head.append("<style>%s</style></head><body><div class=sweep></div>" % _CSS)
    head.append(
        "<header class=topbar><div class=brand>"
        "<span class=orb><i class=orb-aura></i><i class=orb-ring2></i><i class=orb-ring></i>"
        "<i class=orb-sat></i><i class=orb-core></i></span>" + bname +
        "<span class=orbname>EBE&nbsp;ORB</span></div>"
        "<div class=status><span class=dot></span>EBE ORB ONLINE<span class=sep>·</span>"
        "<span id=clock>--:--:--</span></div></header>")
    head.append("<nav class=nav>%s</nav>" % nav)
    return "".join(head) + "<main class=wrap>" + inner + "</main>" + _JS + "</body></html>"


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


def _onboarding_inner():
    """Clean, generic welcome for a brand-new account — no sample data, no niche."""
    from . import sync as syncmod
    chans = syncmod.configured_channels()
    cmark = lambda n: ("✓ " if n in chans else "○ ") + n
    return (
        "<h2>👋 Welcome to your store</h2>"
        "<div class=card><span class=big>Let's get you live in 3 steps.</span>"
        "<div class=sub>Your dashboard fills in as you add products and connect channels.</div></div>"
        "<div class=metrics>"
        "<div class=metric><div class=k>Step 1</div><div class=v style='font-size:18px'>Add products</div></div>"
        "<div class=metric><div class=k>Step 2</div><div class=v style='font-size:18px'>Connect a channel</div></div>"
        "<div class=metric><div class=k>Step 3</div><div class=v style='font-size:18px'>Publish & sync</div></div>"
        "</div>"
        "<div class=card><b>1 · Add your first product</b>"
        "<div class=sub>Open the <b>Catalog</b> tab → add a product (name, cost, price), "
        "or bulk-import a supplier list.</div>"
        "<div style='margin-top:9px'><a class='btn go' href='/catalog'>Go to Catalog →</a></div></div>"
        "<div class=card><b>2 · Connect a sales channel</b>"
        "<div class=sub>Add your channel keys so EBE syncs live stock, prices, and orders. "
        "Status: %s &nbsp; %s</div></div>"
        "<div class=card><b>3 · Publish & let it run</b>"
        "<div class=sub>Publish your catalog to your store, then autopilot keeps stock true and "
        "raises re-buys on its own.</div></div>"
        % (cmark("shopify"), cmark("amazon"))
    )


def render_home(args):
    """Today page — a clean onboarding welcome for empty accounts, the live board once stocked."""
    from .store import Store, DEFAULT_DB
    db = getattr(args, "db", None) or DEFAULT_DB
    if not Store(db).products():
        return _shell(_ctx_from_args(args), "today", _onboarding_inner())
    return render(_data(args))


# ── RE-BUY page (live database + autobuy) ────────────────────────────────────
def _store_for(args):
    """The tenant's real database. Empty is fine — tabs show clean empty states + an
    'add your catalog' prompt (no niche/sample data, so new accounts start blank)."""
    from .store import Store, DEFAULT_DB
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    return store, bool(store.products()), db


def render_rebuy(args):
    from . import autobuy
    store, live, db = _store_for(args)
    prof = args.profile or "generic"
    proposals = autobuy.plan(store)
    drafts = store.purchase_orders("draft")
    ordered = store.purchase_orders("ordered")
    received = store.purchase_orders("received")[:6]
    pcash = sum(p["cash"] for p in proposals)
    open_cash = sum(po["cash"] for po in drafts + ordered)

    inner = ["<h2>🔁 Restock</h2>"]
    if not live:
        inner.append("<div class=banner>No products yet — add them in the <b>Catalog</b> tab "
                     "to run restock on your real stock.</div>")
    inner.append(
        "<div class=metrics>"
        "<div class='metric alert'><div class=k>Under reorder line</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric'><div class=k>Cash to commit</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric'><div class=k>Open POs</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric go'><div class=k>In transit</div><div class=v data-count='%d'>0</div></div>"
        "</div>" % (len(proposals), round(pcash), len(drafts) + len(ordered), len(ordered)))

    p = urllib.parse.quote(prof)
    sheetbtn = ("<a class='btn ghost sm' href='/sheet?profile=%s'>📄 Order sheet</a>" % p) if (drafts or ordered) else ""
    if sheetbtn:
        inner.append("<div class=card>%s</div>" % sheetbtn)
    if proposals:
        raiseall = ("<a class='btn go sm' href='/po?raiseall=1&profile=%s'>⚡ Raise all drafts</a>" % p) if live else ""
        saved = sum(pr.get("savings") or 0 for pr in proposals)
        won = (" · <span class=ok>vendor auction saved $%.0f</span>" % saved) if saved else ""
        inner.append("<h2>📉 Proposed re-buys %s</h2>%s" % (raiseall, ("<div class=sub>%s</div>" % won.strip(" ·")) if won else ""))
        inner.append("<table><tr><th>product<th>vendor<th class=r>on hand<th class=r>cover<th class=r>order<th class=r>cash<th class=r>saved%s</tr>"
                     % ("<th>act" if live else ""))
        for pr in proposals:
            act = ("<td><a class='btn sm' href='/po?raise=%s&profile=%s'>Approve</a>"
                   % (urllib.parse.quote(pr["sku"]), p)) if live else ""
            vendor = pr.get("supplier") or "—"
            if pr.get("bids", 0) > 1:
                vendor = "🏆 %s <span class=sub>(%d bids)</span>" % (_esc(vendor), pr["bids"])
            else:
                vendor = _esc(vendor)
            sv = ("$%.0f" % pr["savings"]) if pr.get("savings") else "—"
            inner.append("<tr><td>%s<td>%s<td class=r>%d<td class=r>%.0fd<td class=r>%d<td class=r>$%.0f<td class=r>%s%s</tr>"
                         % (_esc(pr["name"]), vendor, pr["on_hand"], pr["cover_days"], pr["qty"], pr["cash"], sv, act))
        inner.append("</table>")
    else:
        inner.append("<div class=card><span class=ok>✓ Every SKU has cover</span> — nothing under the reorder line right now.</div>")

    if drafts:
        inner.append("<h2>📝 Draft POs — awaiting approval</h2>")
        inner.append("<table><tr><th>PO<th>product<th class=r>units<th class=r>cash<th>why%s</tr>" % ("<th>act" if live else ""))
        for po in drafts:
            act = ("<td><a class='btn sm' href='/po?order=%d&profile=%s'>Mark ordered</a> "
                   "<a class='btn ghost sm' href='/po?cancel=%d&profile=%s'>Cancel</a>" % (po["id"], p, po["id"], p)) if live else ""
            inner.append("<tr><td>#%d<td>%s<td class=r>%d<td class=r>$%.0f<td class=sub>%s%s</tr>"
                         % (po["id"], _esc(po["name"]), po["qty"], po["cash"], _esc(po["reason"] or ""), act))
        inner.append("</table>")

    if ordered:
        inner.append("<h2>🚚 In transit — receive when it lands</h2>")
        inner.append("<table><tr><th>PO<th>product<th class=r>units<th class=r>cash%s</tr>" % ("<th>act" if live else ""))
        for po in ordered:
            act = ("<td><a class='btn go sm' href='/po?receive=%d&profile=%s'>Receive</a>" % (po["id"], p)) if live else ""
            inner.append("<tr><td>#%d<td>%s<td class=r>%d<td class=r>$%.0f%s</tr>"
                         % (po["id"], _esc(po["name"]), po["qty"], po["cash"], act))
        inner.append("</table>")

    if received:
        inner.append("<h2>📦 Recently received</h2><table><tr><th>PO<th>product<th class=r>units<th class=r>cash</tr>")
        for po in received:
            inner.append("<tr><td>#%d<td>%s<td class=r>+%d<td class=r>$%.0f</tr>"
                         % (po["id"], _esc(po["name"]), po["qty"], po["cash"]))
        inner.append("</table>")
    return _shell(_ctx_from_args(args), "rebuy", "".join(inner), refresh=True)


def _do_po(args, qs):
    """Apply a re-buy action against the real database. Returns nothing (caller redirects)."""
    from .store import Store, DEFAULT_DB
    from . import autobuy
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    if not store.products():
        return                                   # demo db: nothing to act on
    try:
        if qs.get("raiseall"):
            autobuy.scan(store)
        elif qs.get("raise"):
            autobuy.raise_for(store, qs["raise"][0])
        elif qs.get("order"):
            store.mark_ordered(int(qs["order"][0]))
        elif qs.get("receive"):
            store.receive_po(int(qs["receive"][0]))
        elif qs.get("cancel"):
            store.cancel_po(int(qs["cancel"][0]))
    except (ValueError, KeyError):
        pass


# ── CATALOG page (manage products + publish to channels, all from EBE) ───────
def render_catalog(args, msg=""):
    from .store import Store, DEFAULT_DB
    from . import sync as syncmod
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    prods = store.products()
    p = urllib.parse.quote(args.profile or "generic")
    chans = syncmod.configured_channels()
    shop_on = "shopify" in chans

    inner = ["<h2>📦 Catalog — your single source of truth</h2>"]
    inner.append("<div class=sub>Add a product once here, push it to your channels. No spreadsheets, no logging into Shopify.</div>")
    if msg:
        inner.append("<div class='card %s'>%s</div>" % ("ok" if not msg.startswith("✕") else "warn", _esc(msg)))

    inv = sum((pr.get("on_hand") or 0) * (pr.get("cost") or 0) for pr in prods)
    inner.append(
        "<div class=metrics>"
        "<div class=metric><div class=k>Products</div><div class=v data-count='%d'>0</div></div>"
        "<div class=metric><div class=k>Inventory value</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric %s'><div class=k>Shopify</div><div class=v style='font-size:20px'>%s</div></div>"
        "</div>" % (len(prods), round(inv), "go" if shop_on else "alert",
                    "connected" if shop_on else "off"))

    # channel actions
    if shop_on:
        inner.append(
            "<div class=card>"
            "<a class='btn go' href='/catalog-publish?profile=%s'>⬆ Publish new → Shopify</a> "
            "<a class='btn' href='/catalog-publish?update=1&profile=%s'>↻ Update listings</a> "
            "<a class='btn' href='/catalog-describe?profile=%s'>✨ AI write descriptions</a> "
            "<a class='btn' href='/catalog-sync?profile=%s'>🔄 Sync from Shopify</a>"
            "<div class=sub>Publish creates products missing from Shopify; Update refreshes "
            "title/description/price/photo on existing ones (needs write_products). "
            "AI writes descriptions for products missing one. "
            "Sync pulls live stock + price back into EBE.</div></div>" % (p, p, p, p))
    else:
        inner.append("<div class='card warn'>Shopify not connected — add SHOPIFY_STORE + "
                     "SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET to .env, then this tab can publish & sync.</div>")

    # add / update form (GET so it matches the dashboard's action pattern)
    inner.append("""
<div class=card>
<h2 style='margin-top:0'>＋ Add / update a product</h2>
<form action='/catalog-add' method=get class=addform>
  <input type=hidden name=profile value='%s'>
  <input name=sku placeholder='SKU (e.g. COCO-CHARCOAL-1.2KG)' required>
  <input name=name placeholder='Product name'>
  <input name=cost type=number step='0.01' placeholder='Cost $'>
  <input name=sell type=number step='0.01' placeholder='Sell $'>
  <input name=on_hand type=number placeholder='On hand'>
  <input name=monthly type=number placeholder='Sales / mo'>
  <input name=image placeholder='Image URL' style='min-width:220px'>
  <input name=description placeholder='Description' style='min-width:280px;flex:1'>
  <button class='btn go' type=submit>Save</button>
</form>
<div class=sub>Existing SKU? Only the fields you fill change — the rest stay as they were.</div>
</div>
<style>
.addform{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.addform input{font:600 13px var(--hud);color:#eaffff;background:#04141b;border:1px solid #1f4a57;
  border-radius:8px;padding:9px 11px;min-width:130px}
.addform input:focus{outline:none;border-color:var(--cyan)}
.addform input::placeholder{color:#5d8794}
</style>""" % p)

    if prods:
        inner.append("<h2>Your products</h2>")
        inner.append("<table><tr><th>SKU<th>name<th class=r>cost<th class=r>sell<th class=r>on hand<th class=r>/mo<th class=r>margin</tr>")
        for pr in prods:
            cost, sell = pr.get("cost") or 0, pr.get("sell") or 0
            margin = ((sell - cost) / sell * 100) if sell else 0
            mcls = "ok" if margin >= 30 else ("warn" if margin >= 10 else "alert")
            inner.append("<tr><td><b>%s</b><td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>%d<td class=r>%d<td class='r %s'>%.0f%%</tr>"
                         % (_esc(pr["sku"]), _esc(pr.get("name") or ""), cost, sell,
                            pr.get("on_hand") or 0, pr.get("monthly_sales") or 0, mcls, margin))
        inner.append("</table>")
    else:
        inner.append("<div class=card>No products yet — add your first one above.</div>")
    return _shell(_ctx_from_args(args), "catalog", "".join(inner))


def _do_catalog_add(args, qs):
    """Upsert one product from the form. Returns a status message."""
    from .store import Store, DEFAULT_DB
    sku = (qs.get("sku") or [""])[0].strip()
    if not sku:
        return "✕ SKU is required"
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    existing = store.product(sku)
    row = dict(existing) if existing else {}
    row["sku"] = sku
    for field, col, cast in (("name", "name", str), ("cost", "cost", float), ("sell", "sell", float),
                             ("on_hand", "on_hand", int), ("monthly", "monthly_sales", int),
                             ("description", "description", str), ("image", "image_url", str)):
        raw = (qs.get(field) or [""])[0].strip()
        if raw:
            try:
                row[col] = cast(raw)
            except ValueError:
                pass
    store.upsert_products([row])
    return "%s %s" % ("✓ updated" if existing else "✓ added", sku)


def _do_catalog_publish(args, update=False):
    """Publish the catalog to Shopify (update=True also refreshes existing listings)."""
    from .store import Store, DEFAULT_DB
    from .publish import publish_catalog
    from .adapters.shopify import ShopifyClient
    db = getattr(args, "db", None) or DEFAULT_DB
    try:
        res = publish_catalog(Store(db), ShopifyClient(), update=update)
    except Exception as e:
        return "✕ publish failed: %s" % e
    bits = "✓ %d created, %d updated, %d unchanged" % (
        len(res["created"]), len(res.get("updated", [])), len(res["skipped"]))
    if res["failed"]:
        bits += ", %d failed (%s)" % (len(res["failed"]), res["failed"][0][1][:60])
    return bits


def _do_catalog_describe(args):
    """Have Claude write descriptions for products missing one. Returns a status message."""
    from .store import Store, DEFAULT_DB
    from . import copywriter
    db = getattr(args, "db", None) or DEFAULT_DB
    try:
        res = copywriter.describe_into_store(Store(db))
    except Exception as e:
        return "✕ AI describe failed: %s" % e
    msg = "✓ wrote %d description(s), %d already had one" % (len(res["written"]), len(res["skipped"]))
    if res["failed"]:
        msg += ", %d failed (%s)" % (len(res["failed"]), res["failed"][0][1][:60])
    return msg


def _do_catalog_sync(args):
    """Pull live Shopify stock + price into EBE. Returns a status message."""
    from .store import Store, DEFAULT_DB
    from .sync import sync_stock
    from .adapters.shopify import ShopifyClient
    db = getattr(args, "db", None) or DEFAULT_DB
    try:
        res = sync_stock(Store(db), ShopifyClient(), prices=True)
    except Exception as e:
        return "✕ sync failed: %s" % e
    return "✓ synced — %d SKU(s) updated, %d unknown" % (len(res["updated"]), len(res["unknown"]))


# ── MEMBERSHIP page (tier by monthly revenue) ────────────────────────────────
def render_membership(args):
    from .store import Store, DEFAULT_DB
    from . import membership as m
    db = getattr(args, "db", None) or DEFAULT_DB
    s = m.status(Store(db))
    t, nxt = s["tier"], s["next"]
    money = lambda v: "{:,.0f}".format(v or 0)

    inner = ["<h2>👑 EBE Membership</h2>"]
    inner.append(
        "<div class=card style='text-align:center'>"
        "<div style='font-size:48px;line-height:1'>%s</div>"
        "<div class=big style='margin-top:6px'>%s MEMBER</div>"
        "<div class=sub>$%s revenue · last %d days</div></div>"
        % (t["icon"], _esc(t["name"].upper()), money(s["revenue"]), s["days"]))

    if nxt:
        pct = int(round(s["progress"] * 100))
        inner.append(
            "<div class=card><div class=sub>%d%% to %s %s — <b>$%s</b> to go</div>"
            "<div style='height:15px;border-radius:9px;background:#04141b;border:1px solid #1f4a57;"
            "overflow:hidden;margin-top:9px'>"
            "<div style='height:100%%;width:%d%%;background:linear-gradient(90deg,#39e6ff,#7dffce);"
            "box-shadow:0 0 14px rgba(57,230,255,.6)'></div></div></div>"
            % (pct, nxt["icon"], _esc(nxt["name"]), money(s["to_next"]), pct))
    else:
        inner.append("<div class='card go' style='text-align:center'>👑 You're at the top — Elite Diamond status.</div>")

    inner.append("<table><tr><th>tier<th class=r>monthly revenue<th>unlocks</tr>")
    for ti in m.TIERS[1:]:
        on = ti["key"] == t["key"]
        rs = " style='background:rgba(57,230,255,.10)'" if on else ""
        inner.append("<tr%s><td><b>%s %s</b>%s<td class=r>$%s+<td class=sub>%s</tr>"
                     % (rs, ti["icon"], _esc(ti["name"]), " ←" if on else "",
                        money(ti["min"]), _esc(ti["perks"])))
    inner.append("</table>")
    inner.append("<div class=sub>Tier = your trailing 30-day sales revenue. Keep selling to level up — "
                 "and to keep your status. 💪</div>")
    return _shell(_ctx_from_args(args), "membership", "".join(inner))


# ── P&L page (realized profit from recorded sales) ───────────────────────────
def render_pnl(args):
    from . import pnl as pnlmod
    store, live, db = _store_for(args)
    days = 30
    data = pnlmod.compute(store, days=days)
    t = data["totals"]
    inner = ["<h2>📈 Profit &amp; Loss <span class=sub>(last %d days)</span></h2>" % days]
    if not live:
        inner.append("<div class=banner>No products yet — add them in the <b>Catalog</b> tab, "
                     "then sync your sales to see real profit.</div>")
    inner.append(
        "<div class=metrics>"
        "<div class=metric><div class=k>Revenue</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class=metric><div class=k>COGS</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric go'><div class=k>Gross profit</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class=metric><div class=k>Margin</div><div class=v style='font-size:22px'>%.0f%%</div></div>"
        "</div>" % (round(t["revenue"]), round(t["cogs"]), round(t["gross"]), t["margin"] * 100))

    if data["rows"]:
        inner.append("<table><tr><th>product<th class=r>units<th class=r>revenue"
                     "<th class=r>COGS<th class=r>gross<th class=r>margin</tr>")
        for r in data["rows"]:
            mcls = "ok" if r["margin"] >= 0.3 else ("warn" if r["margin"] >= 0.1 else "alert")
            inner.append("<tr><td>%s<td class=r>%d<td class=r>$%.2f<td class=r>$%.2f"
                         "<td class=r>$%.2f<td class='r %s'>%.0f%%</tr>"
                         % (_esc(r["name"][:28]), r["units"], r["revenue"], r["cogs"],
                            r["gross"], mcls, r["margin"] * 100))
        inner.append("</table>")
    else:
        inner.append("<div class=card>No sales recorded yet. Connect a channel and sync your orders, "
                     "and your profit will appear here.</div>")
    return _shell(_ctx_from_args(args), "pnl", "".join(inner))


# ── EBE ORB REPORT page (AI executive rundown + catalog score) ───────────────
def render_report(args):
    from . import report as reportmod
    from .fees import PRESETS
    store, live, db = _store_for(args)
    prof = args.profile or "generic"
    p = urllib.parse.quote(prof)
    data = reportmod.compose(store, profile=prof, fee=PRESETS[args.fees])
    summ = data["summary"]

    inner = ["<h2>🔮 EBE Orb · Business report</h2>"]
    if not live:
        inner.append("<div class=banner>No products yet — add them in the <b>Catalog</b> tab "
                     "to report on your real numbers.</div>")

    if getattr(args, "ai", False):
        try:
            rep = reportmod.write(data)
            prio = "".join("<li>%s</li>" % _esc(x) for x in rep.get("priorities", []))
            focus = rep.get("product_focus", "")
            inner.append(
                "<div class=card><div class=sub>🔮 EBE ORB</div>"
                "<span class=big>%s</span><p>%s</p>%s%s</div>"
                % (_esc(rep.get("headline", "")), _esc(rep.get("summary", "")),
                   ("<p class=sub>➡️ PRIORITIES</p><ul>%s</ul>" % prio) if prio else "",
                   ("<p><b>🎯 Product focus:</b> %s</p>" % _esc(focus)) if focus else ""))
        except Exception as ex:
            inner.append("<div class='card warn'>EBE Orb report isn't available yet "
                         "<span class=sub>(AI not configured)</span></div>")
    else:
        inner.append("<div class=card><a class='btn go' href='/report?profile=%s&ai=1'>🔮 Ask EBE Orb to brief me</a> "
                     "<span class=sub>Claude writes the executive report from your live numbers</span></div>" % p)

    inner.append(
        "<div class=metrics>"
        "<div class=metric><div class=k>Products</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric go'><div class=k>CORNER</div><div class=v data-count='%d'>0</div></div>"
        "<div class=metric><div class=k>STRONG</div><div class=v data-count='%d'>0</div></div>"
        "<div class=metric><div class=k>Profit potential</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "</div>" % (summ["count"], summ["corner"], summ["strong"], round(summ["monthly_profit"])))

    inner.append("<h2>📊 Catalog score <span class=sub>(fees %s)</span></h2>" % _esc(data["fee"]))
    inner.append("<table><tr><th>product<th class=r>cost<th class=r>sell<th class=r>margin"
                 "<th class=r>edge<th>verdict<th class=r>$/mo</tr>")
    for r in data["ranked"]:
        vcls = "ok" if r["verdict"] in ("CORNER", "STRONG") else ("warn" if r["verdict"] == "TEST" else "alert")
        inner.append("<tr><td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>%.0f%%<td class=r>%.0f%%"
                     "<td class=%s>%s<td class=r>$%.0f</tr>"
                     % (_esc(r["name"][:28]), r["cost"], r["sell"], r["margin"] * 100,
                        r["composite"] * 100, vcls, r["verdict"], r["monthly_profit"]))
    inner.append("</table>")
    return _shell(_ctx_from_args(args), "report", "".join(inner))


# ── BRIEF page (the morning rundown) ─────────────────────────────────────────
def render_brief(args):
    from . import brief as briefmod
    from .fees import PRESETS
    import datetime
    store, live, db = _store_for(args)
    b = briefmod.compose(store, profile=args.profile or "generic", fee=PRESETS[args.fees])
    prof = args.profile or "generic"
    p = urllib.parse.quote(prof)
    date = datetime.date.today().strftime("%A %d %B %Y")

    inner = ["<h2>🛰️ Morning brief · %s</h2>" % _esc(date)]
    want_ai = getattr(args, "ai", False)
    if want_ai:
        from .ai.narrator import narrate
        try:
            n = narrate(b)
            prio = "".join("<li>%s</li>" % _esc(x) for x in n.get("priorities", []))
            inner.append("<div class=card><div class=sub>🧠 EBE · AI brief</div>"
                         "<span class=big>%s</span><p>%s</p>%s</div>"
                         % (_esc(n.get("headline", "")), _esc(n.get("narrative", "")),
                            ("<ul>%s</ul>" % prio) if prio else ""))
        except Exception as ex:
            inner.append("<div class='card warn'>AI brief unavailable: %s</div>" % _esc(str(ex)))
    else:
        inner.append("<div class=card><a class='btn' href='/brief?profile=%s&ai=1'>🧠 Ask EBE Orb to brief me</a></div>"
                     % urllib.parse.quote(prof))
    if not live:
        inner.append("<div class=banner>No products yet — add them in the <b>Catalog</b> tab "
                     "to brief on your real stock.</div>")
    inner.append("<div class=card><span class=big>Good morning.</span> Systems online.</div>")
    inner.append(
        "<div class=metrics>"
        "<div class='metric'><div class=k>SKUs tracked</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric alert'><div class=k>Under reorder line</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric'><div class=k>Cash to commit</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric'><div class=k>On-hand value</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric go'><div class=k>In transit</div><div class=v data-count='%d'>0</div></div>"
        "</div>" % (b["products"], b["low"], round(b["cash_to_commit"]), round(b["inv_value"]), b["ordered"]))

    if b.get("cash"):
        c = b["cash"]
        inner.append(
            "<div class=metrics>"
            "<div class='metric go'><div class=k>Stripe available</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
            "<div class='metric'><div class=k>Revenue · 30d</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
            "<div class='metric'><div class=k>Charges · 30d</div><div class=v data-count='%d'>0</div></div>"
            "</div>" % (round(c["available"]), round(c["revenue30"]), c["charges30"]))

    sub = b.get("subs")
    if sub and sub["active"]:
        inner.append(
            "<div class=metrics>"
            "<div class='metric go'><div class=k>Recurring revenue · MRR</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
            "<div class='metric'><div class=k>Committed buys · /mo</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
            "<div class='metric alert'><div class=k>Subscriptions due</div><div class=v data-count='%d'>0</div></div>"
            "</div>" % (round(sub["mrr_sell"]), round(sub["mrr_buy"]), sub["due_count"]))

    inner.append("<div class=card><b>➡️ One move that matters today</b><br><span class=big>%s</span></div>" % _esc(b["move"]))

    actions = []
    if b["low"]:
        actions.append("<a class='btn sm' href='/rebuy?profile=%s'>🚚 %d re-buys → review</a>" % (p, b["low"]))
    if b["drafts"]:
        actions.append("<a class='btn go sm' href='/sheet?profile=%s'>📄 %d order(s) → send</a>" % (p, b["drafts"]))
    if actions:
        inner.append("<div class=card>%s</div>" % " ".join(actions))

    if b["top"]:
        inner.append("<h2>🚚 Top re-buys</h2><table><tr><th>product<th class=r>units<th class=r>cash<th class=r>cover</tr>")
        for t in b["top"]:
            inner.append("<tr><td>%s<td class=r>%d<td class=r>$%.0f<td class=r>%.0fd</tr>"
                         % (_esc(t["name"]), t["qty"], t["cash"], t["cover_days"]))
        inner.append("</table>")

    if b["watch"]:
        inner.append("<h2>🧭 On the radar</h2><table><tr><th>product<th class=r>EDGE<th class=r>moat<th>verdict</tr>")
        for e in b["watch"]:
            inner.append("<tr><td>%s<td class=r>%.0f%%<td class=r>%.0f%%<td><span class='pill %s'>%s</span></tr>"
                         % (_esc(e.item["name"]), e.composite * 100, e.moat * 100, e.verdict, e.verdict))
        inner.append("</table>")
    return _shell(_ctx_from_args(args), "brief", "".join(inner), refresh=not want_ai)


# ── ACT page (propose → approve → execute) ───────────────────────────────────
def render_act(args):
    from . import actions
    store, live, db = _store_for(args)
    prof = args.profile or "generic"
    p = urllib.parse.quote(prof)
    acts = actions.propose(store)
    summ = actions.summarize(acts)

    inner = ["<h2>⚡ Actions · approve the day's moves</h2>"]
    if not live:
        inner.append("<div class=banner>Sample catalog — load yours to act on real stock. "
                     "Approvals are disabled here.</div>")
    inner.append(
        "<div class=metrics>"
        "<div class='metric'><div class=k>Proposed moves</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric alert'><div class=k>Cash out</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "<div class='metric go'><div class=k>Cash in</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "</div>" % (summ["count"], round(summ["cash_out"]), round(summ["cash_in"])))

    if not acts:
        inner.append("<div class=card><span class=ok>✓ All clear</span> — nothing to action right now.</div>")
        return _shell(_ctx_from_args(args), "act", "".join(inner), refresh=True)

    if live:
        inner.append("<div class=card><a class='btn go' href='/do?all=1&profile=%s'>⚡ Approve all %d</a> "
                     "<span class=sub>or approve individually below</span></div>" % (p, len(acts)))
    inner.append("<table><tr><th>move<th class=r>impact<th>flow%s</tr>" % ("<th>approve" if live else ""))
    for a in acts:
        flow = "<span class=ok>↑ in</span>" if a.get("flow") == "in" else "↓ out"
        act = ("<td><a class='btn sm' href='/do?act=%s&profile=%s'>Approve</a>"
               % (urllib.parse.quote(a["id"]), p)) if live else ""
        inner.append("<tr><td>%s<td class=r>$%.0f<td>%s%s</tr>" % (_esc(a["label"]), a["impact"], flow, act))
    inner.append("</table>")
    return _shell(_ctx_from_args(args), "act", "".join(inner), refresh=True)


def _do_act(args, qs):
    """Execute approved action(s) against the real database."""
    from .store import Store, DEFAULT_DB
    from . import actions
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    if not store.products():
        return
    if qs.get("all"):
        actions.execute(store, [a["id"] for a in actions.propose(store)])
    elif qs.get("act"):
        actions.execute(store, [qs["act"][0]])


# ── REPRICE page (competitive pricing vs live market) ────────────────────────
def render_reprice(args):
    from .repricer import reprice_catalog, live_prices_by_sku
    from .fees import PRESETS
    store, live, db = _store_for(args)
    prof = args.profile or "generic"
    p = urllib.parse.quote(prof)
    strategy = getattr(args, "strategy", None) or "undercut"
    fee = PRESETS[args.fees]
    prods = store.products()

    prices, src = {}, "floor only — no competitor data"
    try:
        kp = live_prices_by_sku(prods, _keepa_fetch())
        if kp:
            prices, src = kp, "live · Keepa"
    except Exception:
        pass
    recs = reprice_catalog(prods, prices, fee, strategy=strategy)
    movers = [r for r in recs if abs(r["move"]) >= 0.01]
    uplift = sum(r["move"] for r in recs if r["move"] > 0)

    inner = ["<h2>🏷️ Pricing · %s</h2>" % _esc(strategy)]
    if not live:
        inner.append("<div class=banner>Sample catalog — add an <b>asin</b> column to your products "
                     "for live Keepa pricing. Strategy &amp; floor still compute now.</div>")
    inner.append("<form class=card action='/reprice' method=get><input type=hidden name=profile value='%s'>"
                 "strategy: <select name=strategy onchange='this.form.submit()'>%s</select> "
                 "<span class=sub>source: %s</span></form>"
                 % (_esc(prof), "".join("<option%s>%s</option>" % (" selected" if s == strategy else "", s)
                                        for s in ("undercut", "match", "premium")), _esc(src)))
    inner.append(
        "<div class=metrics>"
        "<div class='metric'><div class=k>SKUs priced</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric alert'><div class=k>Price moves</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric go'><div class=k>Monthly upside</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "</div>" % (len(recs), len(movers), round(uplift * 30)))

    inner.append("<table><tr><th>product<th class=r>now<th class=r>→ rec<th class=r>floor<th class=r>ROI<th>why%s</tr>"
                 % ("<th>act" if live else ""))
    for r in recs:
        flag = "⚓" if r["at_floor"] else ("↑" if r["move"] > 0 else ("↓" if r["move"] < 0 else "="))
        act = ""
        if live and abs(r["move"]) >= 0.01:
            act = "<td><a class='btn sm' href='/price?apply=%s&to=%.2f&profile=%s'>Apply</a>" % (
                urllib.parse.quote(r["sku"]), r["recommended"], p)
        elif live:
            act = "<td><span class=sub>—</span>"
        inner.append("<tr><td>%s<td class=r>$%.2f<td class=r><b>$%.2f</b> %s<td class=r>$%.2f<td class=r>%.0f%%<td class=sub>%s%s</tr>"
                     % (_esc(r["name"]), r["current"], r["recommended"], flag, r["floor"], r["roi"] * 100, _esc(r["reason"]), act))
    inner.append("</table>")
    return _shell(_ctx_from_args(args), "reprice", "".join(inner), refresh=True)


def _keepa_fetch():
    """Return KeepaClient().fetch, or a function yielding nothing if Keepa isn't configured."""
    try:
        from .adapters.keepa import KeepaClient
        return KeepaClient().fetch
    except Exception:
        return lambda asins: []


def _do_price(args, qs):
    """Apply a recommended price to a SKU in the real database."""
    from .store import Store, DEFAULT_DB
    db = getattr(args, "db", None) or DEFAULT_DB
    store = Store(db)
    sku = (qs.get("apply") or [""])[0]
    try:
        to = float((qs.get("to") or ["0"])[0])
    except ValueError:
        return
    p = store.product(sku)
    if p and to > 0:
        store.upsert_products([{**p, "sell": to}])


# ── ORDER SHEET view (sendable POs grouped by supplier) ──────────────────────
def render_sheet(args):
    from .purchasing import orders_by_supplier
    store, live, db = _store_for(args)
    groups = orders_by_supplier(store, ("draft", "ordered"))
    inner = ["<h2>📄 Order sheets · by supplier</h2>"]
    if not groups:
        inner.append("<div class=card><span class=ok>✓ No open orders</span> — nothing to send right now.</div>")
        return _shell(_ctx_from_args(args), "rebuy", "".join(inner))
    grand = 0.0
    for supplier in sorted(groups, key=lambda s: (s == "", s.lower())):
        pos = groups[supplier]
        contact = store.supplier(supplier) if supplier else None
        sub = sum(po["cash"] for po in pos)
        grand += sub
        head = _esc(supplier or "Unassigned supplier")
        inner.append("<div class=card><b class=big>%s</b>" % head)
        if contact:
            bits = " · ".join(_esc(x) for x in (contact.get("email"), contact.get("phone"), contact.get("link")) if x)
            if bits:
                inner.append("<br><span class=sub>%s</span>" % bits)
            if contact.get("min_order"):
                inner.append(" <span class=sub>· min $%.0f</span>" % contact["min_order"])
        elif supplier:
            inner.append("<br><span class=warn>No contact on file — add suppliers.csv</span>")
        inner.append("<table><tr><th>PO<th>SKU<th>item<th class=r>qty<th class=r>unit<th class=r>total</tr>")
        for po in sorted(pos, key=lambda x: x["id"]):
            inner.append("<tr><td>#%d<td>%s<td>%s<td class=r>%d<td class=r>$%.2f<td class=r>$%.2f</tr>"
                         % (po["id"], _esc(po["sku"]), _esc(po["name"]), po["qty"], po["unit_cost"], po["cash"]))
        inner.append("<tr><td colspan=5 class=r><b>Subtotal</b><td class=r><b>$%.2f</b></tr></table></div>" % sub)
    inner.append("<div class=card><span class=big>TOTAL TO AUTHORISE: $%.0f</span> · %d supplier(s)</div>"
                 % (grand, len(groups)))
    return _shell(_ctx_from_args(args), "rebuy", "".join(inner))


# ── SOURCE page (rank candidate products before you buy) ─────────────────────
_SAMPLE_CANDIDATES = ("Private-label coconut charcoal 1kg,hookah,3.20,14.99,420,0.35\n"
                      "Disposable hookah mouth tips 100pk,hookah,1.80,9.99,650,0.30\n"
                      "Branded to-go boxes 50pk,supply,4.50,12.99,500,0.55\n"
                      "Embroidered dad cap,apparel,7.00,24.00,140,0.65\n"
                      "LED bar coaster (light-up),home,2.40,11.99,200,0.80")


def _parse_candidates(text):
    import csv as _csv
    import io as _io
    from .sourcing_rank import _norm
    rows = []
    reader = _csv.reader(_io.StringIO(text))
    for parts in reader:
        if not parts or not parts[0].strip():
            continue
        keys = ["name", "category", "cost", "sell", "monthly_sales", "competition"]
        row = {k: (parts[i] if i < len(parts) else "") for i, k in enumerate(keys)}
        rows.append(_norm(row, parts[0].strip()))
    return rows


def render_source(args, text):
    from .sourcing_rank import rank_candidates, summarize, fund_within_budget
    from .profile import PROFILES
    from .fees import PRESETS
    prof = PROFILES.get(args.profile or "generic") or PROFILES["generic"]
    fee = PRESETS[args.fees]
    text = text or _SAMPLE_CANDIDATES
    inner = ["<h2>🧪 Sourcing · rank candidates before you buy</h2>",
             "<form class=card action='/source' method=get>"
             "<div class=sub>one product per line: <b>name,category,cost,sell,monthly_sales,competition</b></div>"
             "<textarea name=cand>%s</textarea><input type=hidden name=profile value='%s'>"
             "<br><button>Rank candidates</button> <span class=sub>fees: %s</span></form>"
             % (_esc(text), _esc(args.profile or "generic"), _esc(fee.name))]
    ranked = rank_candidates(_parse_candidates(text), prof, fee)
    summ = summarize(ranked)
    plan = fund_within_budget(ranked, getattr(args, "capital", None) or 2000)
    inner.append(
        "<div class=metrics>"
        "<div class='metric'><div class=k>Candidates</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric go'><div class=k>CORNER / STRONG</div><div class=v data-count='%d'>0</div></div>"
        "<div class='metric'><div class=k>Profit potential /mo</div><div class=v data-count='%d' data-pre='$'>$0</div></div>"
        "</div>" % (summ["count"], summ["corner"] + summ["strong"], round(summ["monthly_profit"])))
    inner.append("<table><tr><th>product<th>category<th class=r>cost<th class=r>sell<th class=r>margin<th class=r>EDGE<th>verdict<th class=r>$/mo</tr>")
    for r in ranked:
        inner.append("<tr><td>%s<td>%s<td class=r>$%.2f<td class=r>$%.2f<td class=r>%.0f%%<td class=r>%.0f%%<td><span class='pill %s'>%s</span><td class=r>$%.0f</tr>"
                     % (_esc(r["name"]), _esc(r["category"]), r["cost"], r["sell"], r["margin"] * 100,
                        r["composite"] * 100, r["verdict"], r["verdict"], r["monthly_profit"]))
    inner.append("</table>")
    if plan["chosen"]:
        rows = "".join("<tr><td>%s<td class=r>%d units<td class=r>$%.0f</tr>" % (_esc(c["name"]), c["test_units"], c["test_cash"]) for c in plan["chosen"])
        inner.append("<h2>💰 Fund first (within $%.0f test budget)</h2><table><tr><th>product<th class=r>test batch<th class=r>cash</tr>%s"
                     "<tr><td><b>committed</b><td><td class=r><b>$%.0f</b></tr></table>" % (getattr(args, "capital", None) or 2000, rows, plan["spent"]))
    return _shell(_ctx_from_args(args), "source", "".join(inner))


# ── LIVE EDGE page (Keepa) ───────────────────────────────────────────────────
def render_live(args, asins):
    inner = ["<h2>🧭 Market · competitor prices &amp; arbitrage</h2>",
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
    if qs.get("strategy") and qs["strategy"][0] in ("undercut", "match", "premium"):
        a.strategy = qs["strategy"][0]
    if qs.get("ai"):
        a.ai = qs["ai"][0] in ("1", "true", "yes")
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
            if path == "/po":
                _do_po(args, qs)
                prof = (qs.get("profile") or ["generic"])[0]
                self.send_response(303); self.send_header("Location", "/rebuy?profile=%s" % urllib.parse.quote(prof)); self.end_headers(); return
            if path == "/price":
                _do_price(args, qs)
                prof = (qs.get("profile") or ["generic"])[0]
                self.send_response(303); self.send_header("Location", "/reprice?profile=%s" % urllib.parse.quote(prof)); self.end_headers(); return
            if path == "/do":
                _do_act(args, qs)
                prof = (qs.get("profile") or ["generic"])[0]
                self.send_response(303); self.send_header("Location", "/act?profile=%s" % urllib.parse.quote(prof)); self.end_headers(); return
            if path in ("/catalog-add", "/catalog-publish", "/catalog-sync", "/catalog-describe"):
                a = _req_args(args, query)
                if path == "/catalog-add":
                    msg = _do_catalog_add(a, qs)
                elif path == "/catalog-publish":
                    msg = _do_catalog_publish(a, update=bool(qs.get("update")))
                elif path == "/catalog-describe":
                    msg = _do_catalog_describe(a)
                else:
                    msg = _do_catalog_sync(a)
                prof = (qs.get("profile") or ["generic"])[0]
                loc = "/catalog?profile=%s&msg=%s" % (urllib.parse.quote(prof), urllib.parse.quote(msg))
                self.send_response(303); self.send_header("Location", loc); self.end_headers(); return
            a = _req_args(args, query)
            try:
                if path in ("/", ""):
                    body = render_home(a)
                elif path == "/brief":
                    body = render_brief(a)
                elif path == "/report":
                    body = render_report(a)
                elif path == "/pnl":
                    body = render_pnl(a)
                elif path == "/membership":
                    body = render_membership(a)
                elif path == "/act":
                    body = render_act(a)
                elif path == "/catalog":
                    body = render_catalog(a, (qs.get("msg") or [""])[0])
                elif path == "/rebuy":
                    body = render_rebuy(a)
                elif path == "/reprice":
                    body = render_reprice(a)
                elif path == "/source":
                    body = render_source(a, (qs.get("cand") or [""])[0])
                elif path == "/sheet":
                    body = render_sheet(a)
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
