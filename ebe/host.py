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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import dashboard, tenancy

SECRET = (os.environ.get("EBE_HOST_SECRET") or "ebe-dev-secret-change-me").encode()
OWNER_PW = os.environ.get("EBE_OWNER_PASSWORD")
CHECKOUT_URL = os.environ.get("EBE_CHECKOUT_URL", "")     # your Stripe Payment Link
TRIAL_DAYS = int(os.environ.get("EBE_TRIAL_DAYS", "0"))   # >0 = free trial before payment
BASE_URL = os.environ.get("EBE_BASE_URL", "").rstrip("/")  # e.g. https://os.ebehq.com — for invite links
PORTAL_URL = os.environ.get("EBE_BILLING_PORTAL_URL", "")  # Stripe Customer Portal link (update card / cancel)


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


def _tenant_args(tenant, qs, user=None, role="owner"):
    return types.SimpleNamespace(
        id=tenant["id"], name=tenant["name"], plan=tenant["plan"],
        user=user, role=role,
        fees="amazon-fba", products=None, costs=None, journal=None, capital=None,
        port=None, strategy=None, db=tenant["db_path"],
        profile=(qs.get("profile") or ["generic"])[0])


# write actions a viewer may not perform; team management needs owner/admin
_WRITE_PATHS = ("/po", "/price", "/do",
                "/catalog-add", "/catalog-publish", "/catalog-sync", "/catalog-describe")
_TEAM_PATHS = ("/settings-invite", "/settings-remove")


def _may_write(role, path):
    if path in _TEAM_PATHS:
        return role in ("owner", "admin")
    if path in _WRITE_PATHS:
        return role != "viewer"
    return True


def _invite_link(tid, token):
    q = "/accept?tid=%s&token=%s" % (urllib.parse.quote(tid), token)
    return (BASE_URL + q) if BASE_URL else q


# nav path → key, for plan-gating a hosted tenant's routes
_NAV_KEY = {path: k for path, _lbl, k in dashboard.NAV}


def _upgrade_page(a, nav_key):
    from . import plans
    feat = plans.TAB_FEATURES.get(nav_key)
    need = plans.plan(plans.upgrade_for(feat)) if feat else None
    label = next((lbl for _p, lbl, k in dashboard.NAV if k == nav_key), nav_key)
    msg = ("<h2>🔒 %s is a higher-plan feature</h2>"
           "<div class=card><span class=big>Upgrade to %s</span> to unlock <b>%s</b>."
           "<div style='margin-top:9px'><a class='btn go' href='/settings'>See plans →</a></div></div>"
           % (dashboard._esc(label), dashboard._esc(need["name"] if need else "a higher plan"),
              dashboard._esc(label)))
    return dashboard._shell(dashboard._ctx_from_args(a), nav_key, msg)


def _billing_card(tn, tid, t):
    """The 'add / manage payment information' card. Stripe-hosted — we never touch card data.
    New customers go to Checkout (subscribe); existing ones to the Customer Portal."""
    esc = dashboard._esc
    has_customer = bool(t.get("stripe_customer"))
    cls = "card" if tn.is_entitled(tid) else "card warn"
    btns = []
    if has_customer and PORTAL_URL:
        btns.append("<a class='btn go' href='%s'>Manage billing → update card</a>" % esc(PORTAL_URL))
    if not has_customer and CHECKOUT_URL:
        sep = "&" if "?" in CHECKOUT_URL else "?"
        url = "%s%sclient_reference_id=%s" % (CHECKOUT_URL, sep, urllib.parse.quote(tid))
        btns.append("<a class='btn go' href='%s'>Add payment method → subscribe</a>" % esc(url))
    if not btns:                                   # nothing actionable → tell the operator what to set
        if not (CHECKOUT_URL or PORTAL_URL):
            note = "Billing isn't connected yet. Set EBE_CHECKOUT_URL and EBE_BILLING_PORTAL_URL."
        elif has_customer:
            note = "Set EBE_BILLING_PORTAL_URL to let clients update their card."
        else:
            note = "Set EBE_CHECKOUT_URL to let clients add a payment method."
        btns.append("<span class=sub>%s</span>" % esc(note))
    return ("<div class='%s'><b>💳 Billing</b>"
            "<div class=sub style='margin-top:4px'>subscription: <b>%s</b></div>"
            "<div style='margin-top:10px'>%s</div>"
            "<div class=sub style='margin-top:8px'>Secured by Stripe — cards, bank (ACH) and "
            "Apple/Google Pay. We never see your card number.</div></div>"
            % (cls, esc(tn.status_line(tid)), " ".join(btns)))


def render_tenant_settings(tn, tid, a, msg=""):
    """Full settings for a hosted tenant: business, plan + seats, and team management."""
    from . import plans, dashboard
    esc = dashboard._esc
    t = tn.tenant(tid)
    pl = plans.plan(t["plan"])
    used, cap = tn.seats_used(tid), tn.seat_cap(tid)
    inner = ["<h2>⚙️ Settings</h2>"]
    if msg:
        inner.append("<div class=card>%s</div>" % esc(msg))
    inner.append("<div class=card><b>Business</b><div style='margin-top:6px'><b>%s</b></div>"
                 "<div class=sub>account: %s</div></div>" % (esc(t["name"]), esc(tid)))

    feats = [f for f in plans.FEATURES if plans.includes(t["plan"], f)]
    inner.append("<div class=card><b>Plan</b> · <span class=big>%s</span> &nbsp;$%d/mo"
                 "<div class=sub>seats %d / %d used · %d features unlocked</div></div>"
                 % (esc(pl["name"]), pl["monthly"], used, cap, len(feats)))

    if getattr(a, "role", "owner") == "owner":         # billing is the account owner's alone
        inner.append(_billing_card(tn, tid, t))

    manage = getattr(a, "role", "owner") in ("owner", "admin")
    inner.append("<h2>👥 Team</h2>")
    inner.append("<table><tr><th>email<th>role<th>status<th></tr>")
    inner.append("<tr><td>%s<td>owner<td><span class=ok>active</span><td></tr>" % esc(t["name"]))
    for u in tn.list_users(tid):
        link = ""
        if manage and u["status"] == "invited" and u.get("invite_token"):
            link = ("<div class=sub style='word-break:break-all'>invite: %s</div>"
                    % esc(_invite_link(tid, u["invite_token"])))
        rm = ("<a class='btn ghost sm' href='/settings-remove?uid=%d'>remove</a>" % u["id"]) if manage else ""
        inner.append("<tr><td>%s%s<td>%s<td>%s<td>%s</tr>"
                     % (esc(u["email"]), link, esc(u["role"]), esc(u["status"]), rm))
    inner.append("</table>")

    if manage and tn.can_add_user(tid):
        inner.append(
            "<div class=card><form action='/settings-invite' method=get class=addform>"
            "<input name=email type=email placeholder='teammate@email.com' required>"
            "<select name=role><option>member</option><option>admin</option><option>viewer</option></select>"
            "<button class='btn go' type=submit>Invite</button></form>"
            "<div class=sub>%d of %d seats used.</div></div>" % (used, cap))
    elif manage:
        nxt = plans.next_seat_upgrade(t["plan"])
        up = plans.plan(nxt)["name"] if nxt else "a higher plan"
        inner.append("<div class='card warn'>All %d seats used — upgrade to <b>%s</b> to add more team users.</div>"
                     % (cap, esc(up)))
    return dashboard._shell(dashboard._ctx_from_args(a), "settings", "".join(inner))


def _page(title, inner):
    return ("<!doctype html><meta charset=utf-8><title>%s</title>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<style>%s</style><main class=wrap>%s</main>" % (title, dashboard._CSS, inner))


def _signup_page(msg=""):
    note = "<div class='card warn'>%s</div>" % dashboard._esc(msg) if msg else ""
    trial = " · %d-day free trial" % TRIAL_DAYS if TRIAL_DAYS else ""
    return _page("EBE · Start your venue",
                 "<h2>Start your venue on EBE%s</h2>%s"
                 "<form class=card method=post action='/signup'>"
                 "<label>Venue name</label><input name=name placeholder='Cloud9 Lounge' autofocus><br><br>"
                 "<label>Choose a login ID</label><input name=id placeholder='cloud9'><br><br>"
                 "<label>Email</label><input name=email type=email><br><br>"
                 "<label>Password</label><input name=pw type=password><br><br>"
                 "<button>Create account → checkout</button></form>"
                 "<div class=sub>Already have an account? <a href='/login'>Sign in</a></div>" % (trial, note))


def _login_page(msg=""):
    from . import brand as brandmod
    note = "<div class='card warn'>%s</div>" % dashboard._esc(msg) if msg else ""
    brand = dashboard._esc(brandmod.upper())
    return _page("EBE · Sign in",
                 "<h2>%s · sign in</h2>%s"
                 "<form class=card method=post action='/login'>"
                 "<label>Account ID</label><input name=id placeholder='cloud9' autofocus><br><br>"
                 "<label>Email <span class=sub>(team members only — owners leave blank)</span></label>"
                 "<input name=email type=email placeholder='you@email.com'><br><br>"
                 "<label>Password</label><input name=pw type=password><br><br>"
                 "<button>Sign in</button></form>" % (brand, note))


def _accept_page(tid, token, msg=""):
    note = "<div class='card warn'>%s</div>" % dashboard._esc(msg) if msg else ""
    esc = dashboard._esc
    return _page("EBE · Accept invite",
                 "<h2>Set your password</h2>%s"
                 "<form class=card method=post action='/accept'>"
                 "<input type=hidden name=tid value='%s'>"
                 "<input type=hidden name=token value='%s'>"
                 "<div class=sub>account: <b>%s</b></div><br>"
                 "<label>Choose a password</label><input name=pw type=password autofocus><br><br>"
                 "<button>Activate &amp; sign in</button></form>"
                 % (note, esc(tid), esc(token), esc(tid)))


def _locked_page(tn, tid):
    pay = ""
    if CHECKOUT_URL:
        sep = "&" if "?" in CHECKOUT_URL else "?"
        pay = "<a class='btn' href='%s%sclient_reference_id=%s'>Renew subscription</a> " % (
            CHECKOUT_URL, sep, urllib.parse.quote(tid))
    return _page("EBE · Subscription required",
                 "<h2>⛔ Subscription inactive</h2><div class='card warn'>"
                 "Your EBE subscription is <b>%s</b>. Renew to continue.</div>"
                 "<div class=card>%s<a href='/logout'>sign out</a></div>"
                 % (dashboard._esc(tn.status_line(tid)), pay))


def serve(args):
    # --port wins; else Render/Heroku-style $PORT; else default
    port = getattr(args, "port", None) or int(os.environ.get("PORT") or 8080)

    class H(BaseHTTPRequestHandler):
        @property
        def tn(self):
            # a fresh control-DB connection per request (ThreadingHTTPServer-safe)
            if not getattr(self, "_tn", None):
                self._tn = tenancy.Tenants()
            return self._tn

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

        def _session(self):
            """(tid, email) from the signed cookie. email is None for the owner login."""
            raw = _unsign(_cookie(self.headers.get("Cookie"), "ebe_sess"))
            if not raw:
                return None, None
            tid, _, email = raw.partition("|")
            return tid, (email or None)

        def _session_tenant(self):
            return self._session()[0]

        def _is_owner(self):
            return _unsign(_cookie(self.headers.get("Cookie"), "ebe_owner")) == "OWNER"

        def do_POST(self):
            path, _, _q = self.path.partition("?")
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)
            if path == "/webhook/stripe":                  # Stripe calls this — verify + apply
                from . import billing
                sig = self.headers.get("Stripe-Signature", "")
                if billing.WEBHOOK_SECRET and not billing.verify_signature(raw, sig, billing.WEBHOOK_SECRET):
                    self._send("bad signature", 400); return
                event = billing.parse(raw)
                if event is None:
                    self._send("bad payload", 400); return
                try:
                    billing.handle_event(self.tn, event)
                except Exception:
                    pass
                self._send("ok"); return
            form = urllib.parse.parse_qs(raw.decode("utf-8"))
            g = lambda k: (form.get(k) or [""])[0]
            if path == "/signup":
                tid = g("id").strip().lower()
                if not tid or not g("pw") or not g("name"):
                    self._send(_signup_page("Fill in venue, ID, and password.")); return
                if self.tn.exists(tid):
                    self._send(_signup_page("That login ID is taken — pick another.")); return
                self.tn.create_tenant(tid, g("name"), g("pw"), days=TRIAL_DAYS, plan="pro")
                if TRIAL_DAYS <= 0:
                    self.tn.suspend(tid)                   # no trial → locked until they pay
                if CHECKOUT_URL:
                    sep = "&" if "?" in CHECKOUT_URL else "?"
                    url = "%s%sclient_reference_id=%s&prefilled_email=%s" % (
                        CHECKOUT_URL, sep, urllib.parse.quote(tid), urllib.parse.quote(g("email")))
                    self._redirect(url); return
                self._redirect("/login"); return
            if path == "/login":
                tid = g("id").strip().lower()
                email = g("email").strip().lower()
                if email:                                  # team member sign-in
                    u = self.tn.authenticate_user(tid, email, g("pw"))
                    if u:
                        val = _sign("%s|%s" % (tid, email))
                        self._redirect("/", "ebe_sess=%s; HttpOnly; Path=/; Max-Age=86400" % val)
                    else:
                        self._send(_login_page("Wrong account, email, or password."))
                    return
                if self.tn.authenticate(tid, g("pw")):     # venue owner sign-in
                    self._redirect("/", "ebe_sess=%s; HttpOnly; Path=/; Max-Age=86400" % _sign(tid))
                else:
                    self._send(_login_page("Wrong venue ID or password."))
                return
            if path == "/accept":                          # redeem an invite → set password
                tid = g("tid").strip().lower()
                token, pw = g("token"), g("pw")
                if not pw or len(pw) < 6:
                    self._send(_accept_page(tid, token, "Choose a password of at least 6 characters."))
                    return
                u = self.tn.accept_invite(tid, token, pw)
                if not u:
                    self._send(_accept_page(tid, token, "This invite link is invalid or already used."))
                    return
                val = _sign("%s|%s" % (tid, u["email"]))
                self._redirect("/", "ebe_sess=%s; HttpOnly; Path=/; Max-Age=86400" % val)
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
                    self.tn.create_tenant(tid, g("name") or tid, g("pw") or "changeme", days=int(g("days") or 30))
                elif act == "renew":
                    self.tn.renew(tid, days=int(g("days") or 30))
                elif act == "suspend":
                    self.tn.suspend(tid)
                elif act == "resume":
                    self.tn.resume(tid)
                self._redirect("/admin")
                return
            self._send(_page("?", "<div class=card>bad request</div>"), 400)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            qs = urllib.parse.parse_qs(query)
            if path == "/health":                       # uptime probe — no auth
                self._send("ok"); return
            if path == "/login":
                self._send(_login_page()); return
            if path == "/signup":
                self._send(_signup_page()); return
            if path == "/accept":
                tid = (qs.get("tid") or [""])[0].strip().lower()
                token = (qs.get("token") or [""])[0]
                self._send(_accept_page(tid, token)); return
            if path == "/logout":
                self._redirect("/login", "ebe_sess=; Path=/; Max-Age=0"); return
            if path == "/admin" or path == "/admin/login":
                self._admin(); return

            tid, email = self._session()
            if not tid or not self.tn.tenant(tid):
                self._redirect("/login"); return
            if email and not self.tn.get_user(tid, email):       # team user removed → sign out
                self._redirect("/login", "ebe_sess=; Path=/; Max-Age=0"); return
            if not self.tn.is_entitled(tid):                     # 🔒 server-side subscription gate
                self._send(_locked_page(self.tn, tid), 402); return

            role = (self.tn.user_role(tid, email) or "member") if email else "owner"
            a = _tenant_args(self.tn.tenant(tid), qs, user=email, role=role)
            try:
                body = self._tenant_page(path, a, qs)
            except Exception as ex:
                body = _page("error", "<pre>%s</pre>" % dashboard._esc(str(ex)))
            if body is None:
                self._send(b"", 404); return
            self._send(body)

        def _tenant_page(self, path, a, qs):
            # role guard: viewers can't write; only owner/admin manage the team
            if not _may_write(a.role, path):
                self._redirect("/settings?msg=%s"
                               % urllib.parse.quote("You don't have permission for that."))
                return None
            # write actions: apply to the tenant's own DB, then redirect back
            if path == "/po":
                dashboard._do_po(a, qs); self._redirect("/rebuy?profile=%s" % a.profile); return None
            if path == "/price":
                dashboard._do_price(a, qs); self._redirect("/reprice?profile=%s" % a.profile); return None
            if path == "/do":
                dashboard._do_act(a, qs); self._redirect("/act?profile=%s" % a.profile); return None
            # Team settings actions
            if path == "/settings-invite":
                from .tenancy import SeatLimitError
                email = (qs.get("email") or [""])[0].strip()
                role = (qs.get("role") or ["member"])[0]
                if not email:
                    msg = "Enter an email to invite."
                else:
                    try:
                        token = self.tn.add_user(a.id, email, role)
                        msg = "Invited %s as %s. Share this link: %s" % (
                            email, role, _invite_link(a.id, token))
                    except SeatLimitError:
                        msg = "Seat limit reached — upgrade your plan to add more users."
                self._redirect("/settings?msg=%s" % urllib.parse.quote(msg)); return None
            if path == "/settings-remove":
                self.tn.remove_user(a.id, (qs.get("uid") or ["0"])[0])
                self._redirect("/settings"); return None
            # Catalog write actions — apply to the tenant's own DB, then back to /catalog
            if path in ("/catalog-add", "/catalog-publish", "/catalog-sync", "/catalog-describe"):
                if path == "/catalog-add":
                    msg = dashboard._do_catalog_add(a, qs)
                elif path == "/catalog-publish":
                    msg = dashboard._do_catalog_publish(a, update=bool(qs.get("update")))
                elif path == "/catalog-describe":
                    msg = dashboard._do_catalog_describe(a)
                else:
                    msg = dashboard._do_catalog_sync(a)
                self._redirect("/catalog?profile=%s&msg=%s"
                               % (a.profile, urllib.parse.quote(msg))); return None
            # plan gate: block tabs above the tenant's plan (even via direct URL)
            from . import plans
            nav_key = _NAV_KEY.get(path)
            if nav_key and not plans.tab_allowed(a.plan, nav_key):
                return _upgrade_page(a, nav_key)
            pages = {
                "/": lambda: dashboard.render_home(a),
                "/brief": lambda: dashboard.render_brief(a),
                "/report": lambda: dashboard.render_report(a),
                "/act": lambda: dashboard.render_act(a),
                "/catalog": lambda: dashboard.render_catalog(a, (qs.get("msg") or [""])[0]),
                "/pnl": lambda: dashboard.render_pnl(a),
                "/membership": lambda: dashboard.render_membership(a),
                "/settings": lambda: render_tenant_settings(self.tn, a.id, a, (qs.get("msg") or [""])[0]),
                "/rebuy": lambda: dashboard.render_rebuy(a),
                "/reprice": lambda: dashboard.render_reprice(a),
                "/source": lambda: dashboard.render_source(a, (qs.get("cand") or [""])[0]),
                "/discover": lambda: dashboard.render_discover(a, qs),
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
            for t in self.tn.list_tenants():
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
                               dashboard._esc(self.tn.status_line(t["id"])),
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

    print("EBE HOST (multi-tenant) → http://0.0.0.0:%d   (/login · /admin · /health)" % port)

    # In-process autopilot: run the loop for every entitled tenant on a timer (cloud-safe —
    # shares the web service's disk). Enable with EBE_AUTOPILOT_MINUTES (0/unset = off).
    # Wrapped so a scheduler problem can NEVER stop the web server from booting.
    try:
        mins = int(os.environ.get("EBE_AUTOPILOT_MINUTES") or 0)
    except ValueError:
        mins = 0
    if mins > 0:
        try:
            from . import scheduler, autopilot
            from .store import Store
            sched_tn = tenancy.Tenants()        # dedicated connection for the scheduler thread
            scheduler.start(
                mins,
                tenants=lambda: [t for t in sched_tn.list_tenants() if sched_tn.is_entitled(t["id"])],
                store_factory=lambda t: Store(t["db_path"]),
                cycle_fn=lambda s: autopilot.cycle(s),
            )
            print("[autopilot] in-process scheduler ON · every %dm" % mins)
        except Exception as e:
            print("[autopilot] disabled (start failed, web server still up): %s" % e)

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        print("\nstopped.")
