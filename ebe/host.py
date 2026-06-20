#!/usr/bin/env python3
"""
host.py — HOSTED, MULTI-TENANT EBE. You run one server; each client venue logs in and
sees only their own data. Every request is checked server-side against their subscription
(tenancy.is_entitled) — lapsed clients are locked out and there's no code for them to patch.

  python -m ebe host --port 8080           # run the SaaS server
  EBE_OWNER_PASSWORD=... python -m ebe host    # enable the /admin panel

Routes: /login · /logout · the tenant dashboard (reuses ebe.dashboard pages) · /admin
(owner: create / renew / suspend tenants). Pure stdlib http.server.
"""
from __future__ import annotations

import hashlib
import hmac
import http.cookies
import os
import types
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import dashboard, tenancy

SECRET = (os.environ.get("EBE_HOST_SECRET") or "ebe-dev-secret-change-me").encode()
OWNER_PW = os.environ.get("EBE_OWNER_PASSWORD")


def _sign(value):
    mac = hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()[:32]
    return "%s.%s" % (value, mac)


def _unsign(signed):
    if not signed or "." not in signed:
        return None
    value, mac = signed.rsplit(".", 1)
    return value if hmac.compare_digest(_sign(value).rsplit(".", 1)[1], mac) else None


def _cookie(header, key):
    c = http.cookies.SimpleCookie(header or "")
    return c[key].value if key in c else None


def _tenant_args(tenant, qs):
    return types.SimpleNamespace(
        fees="amazon-fba", products=None, costs=None, journal=None, capital=None,
        port=None, strategy=None, db=tenant["db_path"],
        profile=(qs.get("profile") or ["hookah"])[0])


def _page(title, inner):
    return ("<!doctype html><meta charset=utf-8><title>%s</title>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<style>%s</style><main class=wrap>%s</main>" % (title, dashboard._CSS, inner))


def _login_page(msg=""):
    note = "<div class='card warn'>%s</div>" % dashboard._esc(msg) if msg else ""
    return _page("EBE · Sign in",
                 "<h2>EBE&nbsp;COMMAND · sign in</h2>%s"
                 "<form class=card method=post action='/login'>"
                 "<label>Venue ID</label><input name=id placeholder='cloud9' autofocus><br><br>"
                 "<label>Password</label><input name=pw type=password><br><br>"
                 "<button>Sign in</button></form>" % note)


def _locked_page(tn, tid):
    return _page("EBE · Subscription required",
                 "<h2>⛔ Subscription inactive</h2><div class='card warn'>"
                 "Your EBE subscription is <b>%s</b>. Contact your provider to renew.</div>"
                 "<div class=card><a href='/logout'>sign out</a></div>"
                 % dashboard._esc(tn.status_line(tid)))


def serve(args):
    port = getattr(args, "port", None) or 8080
    tn = tenancy.Tenants()

    class H(BaseHTTPRequestHandler):
        def _send(self, body, code=200, headers=None):
            body = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or []):
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, where, cookie=None):
            h = [("Location", where)]
            if cookie:
                h.append(("Set-Cookie", cookie))
            self._send(b"", 303, h)

        def _session_tenant(self):
            return _unsign(_cookie(self.headers.get("Cookie"), "ebe_sess"))

        def _is_owner(self):
            return _unsign(_cookie(self.headers.get("Cookie"), "ebe_owner")) == "OWNER"

        def do_POST(self):
            path, _, _q = self.path.partition("?")
            length = int(self.headers.get("Content-Length") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            g = lambda k: (form.get(k) or [""])[0]
            if path == "/login":
                tid = g("id").strip().lower()
                if tn.authenticate(tid, g("pw")):
                    self._redirect("/", "ebe_sess=%s; HttpOnly; Path=/; Max-Age=86400" % _sign(tid))
                else:
                    self._send(_login_page("Wrong venue ID or password."))
                return
            if path == "/admin/login":
                if OWNER_PW and hmac.compare_digest(g("pw"), OWNER_PW):
                    self._redirect("/admin", "ebe_owner=%s; HttpOnly; Path=/; Max-Age=86400" % _sign("OWNER"))
                else:
                    self._send(_page("admin", "<div class='card warn'>wrong owner password</div>"))
                return
            if path == "/admin/action" and self._is_owner():
                act = g("act")
                tid = g("id").strip().lower()
                if act == "create" and tid:
                    tn.create_tenant(tid, g("name") or tid, g("pw") or "changeme", days=int(g("days") or 30))
                elif act == "renew":
                    tn.renew(tid, days=int(g("days") or 30))
                elif act == "suspend":
                    tn.suspend(tid)
                elif act == "resume":
                    tn.resume(tid)
                self._redirect("/admin")
                return
            self._send(_page("?", "<div class=card>bad request</div>"), 400)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            if path == "/login":
                self._send(_login_page()); return
            if path == "/logout":
                self._redirect("/login", "ebe_sess=; Path=/; Max-Age=0"); return
            if path == "/admin" or path == "/admin/login":
                self._admin(); return

            tid = self._session_tenant()
            if not tid or not tn.tenant(tid):
                self._redirect("/login"); return
            if not tn.is_entitled(tid):                     # 🔒 server-side subscription gate
                self._send(_locked_page(tn, tid), 402); return

            a = _tenant_args(tn.tenant(tid), qs)
            try:
                body = self._tenant_page(path, a, qs)
            except Exception as ex:
                body = _page("error", "<pre>%s</pre>" % dashboard._esc(str(ex)))
            if body is None:
                self._send(b"", 404); return
            self._send(body)

        def _tenant_page(self, path, a, qs):
            # write actions: apply to the tenant's own DB, then redirect back
            if path == "/po":
                dashboard._do_po(a, qs); self._redirect("/rebuy?profile=%s" % a.profile); return None
            if path == "/price":
                dashboard._do_price(a, qs); self._redirect("/reprice?profile=%s" % a.profile); return None
            if path == "/do":
                dashboard._do_act(a, qs); self._redirect("/act?profile=%s" % a.profile); return None
            pages = {
                "/": lambda: dashboard.render(dashboard._data(a)),
                "/brief": lambda: dashboard.render_brief(a),
                "/act": lambda: dashboard.render_act(a),
                "/rebuy": lambda: dashboard.render_rebuy(a),
                "/reprice": lambda: dashboard.render_reprice(a),
                "/source": lambda: dashboard.render_source(a, (qs.get("cand") or [""])[0]),
                "/sheet": lambda: dashboard.render_sheet(a),
                "/live": lambda: dashboard.render_live(a, (qs.get("asins") or [""])[0]),
                "/supply": lambda: dashboard.render_supply(a, (qs.get("listings") or [""])[0]),
                "/venue": lambda: dashboard.render_venue(a, (qs.get("sales") or [""])[0]),
            }
            fn = pages.get(path)
            return fn() if fn else None

        def _admin(self):
            if not OWNER_PW:
                self._send(_page("admin", "<div class='card warn'>Set EBE_OWNER_PASSWORD to enable /admin.</div>")); return
            if not self._is_owner():
                self._send(_page("admin", "<h2>Owner sign in</h2><form class=card method=post action='/admin/login'>"
                                 "<input name=pw type=password placeholder='owner password'> <button>Enter</button></form>"))
                return
            rows = []
            for t in tn.list_tenants():
                rows.append("<tr><td>%s<td>%s<td>%s<td>"
                            "<form method=post action='/admin/action' style='display:inline'>"
                            "<input type=hidden name=id value='%s'><input type=hidden name=act value='renew'>"
                            "<input name=days size=3 value='30'><button>renew</button></form> "
                            "<form method=post action='/admin/action' style='display:inline'>"
                            "<input type=hidden name=id value='%s'><input type=hidden name=act value='suspend'>"
                            "<button>suspend</button></form> "
                            "<form method=post action='/admin/action' style='display:inline'>"
                            "<input type=hidden name=id value='%s'><input type=hidden name=act value='resume'>"
                            "<button>resume</button></form>"
                            % (dashboard._esc(t["id"]), dashboard._esc(t["name"]),
                               dashboard._esc(tn.status_line(t["id"])),
                               dashboard._esc(t["id"]), dashboard._esc(t["id"]), dashboard._esc(t["id"])))
            create = ("<h2>New tenant</h2><form class=card method=post action='/admin/action'>"
                      "<input type=hidden name=act value='create'>"
                      "ID <input name=id size=10> name <input name=name size=16> "
                      "pw <input name=pw size=10> days <input name=days size=3 value='30'> "
                      "<button>Create</button></form>")
            self._send(_page("EBE admin",
                             "<h2>EBE · tenants</h2><table><tr><th>id<th>name<th>status<th>actions</tr>%s</table>%s"
                             % ("".join(rows), create)))

        def log_message(self, *a):
            pass

    print("EBE HOST (multi-tenant) → http://127.0.0.1:%d   (/login · /admin)" % port)
    srv = HTTPServer(("0.0.0.0", port), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        print("\nstopped.")
