#!/usr/bin/env python3
"""
storefront.py — the PUBLIC supply storefront. Where other venues browse your hospitality
supply catalog and self-subscribe to recurring delivery. Pure stdlib http.server.

A signup here writes straight into the same database — it creates the customer and a
'sell' subscription — so it instantly flows into MRR, the ledger (A/R), statements, and
the Act layer. This is the marketplace front-end of the Hospitality Commerce Network.

  python -m ebe storefront            # serves http://127.0.0.1:8088 (the customer side)
"""
from __future__ import annotations

import html
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

CADENCES = [("7", "Weekly"), ("14", "Every 2 weeks"), ("30", "Monthly")]

_CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:#e9f2ff;font:15px/1.6 ui-sans-serif,system-ui,"Segoe UI",sans-serif;
  background:radial-gradient(1100px 600px at 80% -10%,rgba(33,96,176,.25),transparent 60%),linear-gradient(180deg,#070b14,#0a1322)}
.wrap{max-width:1040px;margin:0 auto;padding:0 22px 70px}
header{display:flex;align-items:center;gap:14px;padding:22px 0 8px;border-bottom:1px solid rgba(86,180,255,.18);margin-bottom:22px}
.dot{width:13px;height:13px;border-radius:50%;background:radial-gradient(circle at 30% 30%,#cffbff,#39e6ff 50%,#0c7d9e);box-shadow:0 0 12px #39e6ff}
h1{font:700 20px/1 ui-monospace,monospace;letter-spacing:.14em;margin:0;color:#eaf8ff}
.tag{color:#88a;font-size:13px}
h2{font:600 13px/1.2 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#bfe9ff;margin:26px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:rgba(17,28,46,.55);border:1px solid rgba(86,180,255,.18);border-radius:15px;padding:16px 18px;backdrop-filter:blur(10px)}
.name{font-weight:700;font-size:16px;color:#eaffff}
.cat{color:#7e93b0;font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.price{font:700 22px/1 ui-monospace,monospace;color:#7dffce;margin:8px 0}
.price small{font-size:12px;color:#88a;font-weight:400}
label{display:block;font-size:12px;color:#9fb4d0;margin:10px 0 4px}
input,select{width:100%;background:rgba(7,13,24,.7);color:#e9f2ff;border:1px solid rgba(86,180,255,.25);border-radius:9px;padding:9px 11px;font:inherit}
.row{display:flex;gap:10px}.row>div{flex:1}
button{width:100%;margin-top:12px;cursor:pointer;font:600 13px/1 ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;
  color:#00121a;background:linear-gradient(180deg,#86f0ff,#39e6ff);border:0;border-radius:10px;padding:11px;box-shadow:0 8px 22px -8px #39e6ff}
.hero{background:rgba(17,28,46,.4);border:1px solid rgba(86,180,255,.18);border-radius:15px;padding:18px 20px;margin-bottom:8px}
.ok{color:#7dffce}.big{font:700 24px/1.2 ui-monospace,monospace;color:#eaffff}
a{color:#9cf}
"""


def b2b_price(p):
    """The listed supply price: the sell price if set, else a markup on landed cost."""
    sell = p.get("sell") or 0
    return round(sell if sell > 0 else (p.get("cost") or 0) * 1.4, 2)


def supply_items(store):
    """Catalog items offered for B2B supply (anything with a real cost)."""
    out = []
    for p in store.products():
        if (p.get("cost") or 0) <= 0:
            continue
        out.append({"sku": p["sku"], "name": p["name"], "category": p.get("category") or "supply",
                    "price": b2b_price(p)})
    out.sort(key=lambda x: x["name"])
    return out


def subscribe(store, venue, email, sku, qty, cadence_days, price):
    """Self-service signup: create/refresh the customer and open a recurring sell-sub."""
    venue = (venue or "").strip()
    if not venue or not store.product(sku):
        return None
    store.upsert_customers([{"name": venue, "email": (email or "").strip(), "terms_days": 14}])
    return store.add_subscription(
        sku=sku, qty=int(qty), cadence_days=int(cadence_days), kind="sell",
        counterparty=venue, unit_price=float(price),
        next_due=time.time() + int(cadence_days) * 86400,
        name="%s — supply" % venue)


def _esc(x):
    return html.escape(str(x))


def _page(inner):
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><title>EBE Supply</title>"
            "<meta name=viewport content='width=device-width,initial-scale=1'><style>%s</style></head><body>"
            "<div class=wrap><header><span class=dot></span><div><h1>EBE&nbsp;SUPPLY</h1>"
            "<div class=tag>hospitality supply network · recurring delivery</div></div></header>"
            "%s</div></body></html>") % (_CSS, inner)


def render_catalog(store):
    items = supply_items(store)
    cards = []
    for it in items:
        opts = "".join("<option value='%s'>%s</option>" % (d, lbl) for d, lbl in CADENCES)
        cards.append(
            "<div class=card><div class=cat>%s</div><div class=name>%s</div>"
            "<div class=price>$%.2f <small>/ unit</small></div>"
            "<form action='/subscribe' method=get>"
            "<input type=hidden name=sku value='%s'><input type=hidden name=price value='%.2f'>"
            "<label>Your venue</label><input name=venue placeholder='Cloud9 Lounge' required>"
            "<label>Email</label><input name=email type=email placeholder='ap@venue.com'>"
            "<div class=row><div><label>Qty / delivery</label><input name=qty type=number min=1 value='100'></div>"
            "<div><label>Cadence</label><select name=cadence>%s</select></div></div>"
            "<button>Start supply plan</button></form></div>"
            % (_esc(it["category"]), _esc(it["name"]), it["price"], _esc(it["sku"]), it["price"], opts))
    hero = ("<div class=hero><div class=big>Reliable supply, on autopilot.</div>"
            "<div class=tag>Set a delivery cadence and we keep you stocked — cups, charcoal, to-go boxes, and more.</div></div>")
    if not items:
        return _page(hero + "<p class=tag>Catalog coming soon.</p>")
    return _page(hero + "<h2>Supply catalog</h2><div class=grid>%s</div>" % "".join(cards))


def render_thanks(store, venue, sku, qty, cadence):
    p = store.product(sku)
    name = p["name"] if p else sku
    cad = dict(CADENCES).get(str(cadence), "%s days" % cadence)
    return _page(
        "<div class=hero><div class=big ok>You're set, %s ✓</div>"
        "<p>We'll deliver <b>%s × %s</b> on a <b>%s</b> schedule. "
        "An invoice will follow each delivery (net 14).</p>"
        "<a href='/'>← Add another supply plan</a></div>"
        % (_esc(venue), _esc(qty), _esc(name), _esc(cad.lower())))


def serve(args):
    from .store import Store, DEFAULT_DB
    db = getattr(args, "db", None) or DEFAULT_DB
    port = getattr(args, "port", None) or 8088

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            store = Store(db)
            try:
                if path == "/subscribe" and qs.get("sku") and qs.get("venue"):
                    sid = subscribe(store, qs["venue"][0], (qs.get("email") or [""])[0],
                                    qs["sku"][0], (qs.get("qty") or ["100"])[0],
                                    (qs.get("cadence") or ["30"])[0], (qs.get("price") or ["0"])[0])
                    body = (render_thanks(store, qs["venue"][0], qs["sku"][0],
                                          (qs.get("qty") or ["100"])[0], (qs.get("cadence") or ["30"])[0])
                            if sid else render_catalog(store))
                else:
                    body = render_catalog(store)
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

    print("EBE SUPPLY storefront → http://127.0.0.1:%d   (Ctrl+C to stop)" % port)
    srv = HTTPServer(("127.0.0.1", port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        print("\nstopped.")
