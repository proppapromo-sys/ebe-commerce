#!/usr/bin/env python3
"""
shopify_auth.py — one-time OAuth handshake for the new Shopify Dev Dashboard apps
(which give a Client ID + Secret instead of a static Admin API token).

  python -m ebe shopify-auth

Opens your browser, you click Install, and EBE captures the Admin API access token and
writes it to .env as SHOPIFY_TOKEN — after which `sync --channel shopify` just works.

Needs in .env:  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET
And the app's allowed redirect URL must include:  http://localhost:8723/callback
"""
from __future__ import annotations

import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import config
from .base import request_json, AdapterError

SCOPES = "read_products,read_inventory,read_orders"
PORT = 8723
REDIRECT = "http://localhost:%d/callback" % PORT


def build_auth_url(store, client_id, state, scopes=SCOPES, redirect=REDIRECT):
    return ("https://%s.myshopify.com/admin/oauth/authorize?client_id=%s&scope=%s&redirect_uri=%s&state=%s"
            % (store, urllib.parse.quote(client_id), urllib.parse.quote(scopes),
               urllib.parse.quote(redirect, safe=""), urllib.parse.quote(state)))


def exchange_code(store, client_id, client_secret, code):
    """Trade the authorization code for a permanent Admin API access token."""
    data = request_json("POST", "https://%s.myshopify.com/admin/oauth/access_token" % store,
                        json_body={"client_id": client_id, "client_secret": client_secret, "code": code})
    token = data.get("access_token")
    if not token:
        raise AdapterError("Shopify did not return an access_token: %s" % data)
    return token


def authorize(store=None, client_id=None, client_secret=None, scopes=SCOPES, open_browser=True):
    store = store or config.get("SHOPIFY_STORE")
    client_id = client_id or config.get("SHOPIFY_CLIENT_ID")
    client_secret = client_secret or config.get("SHOPIFY_CLIENT_SECRET")
    if not all((store, client_id, client_secret)):
        raise AdapterError("need SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET in .env")

    state = secrets.token_urlsafe(16)
    url = build_auth_url(store, client_id, state, scopes)
    holder = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if qs.get("code") and qs.get("state", [""])[0] == state:
                holder["code"] = qs["code"][0]
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
                self.wfile.write(b"<h2>EBE connected to Shopify.</h2><p>You can close this tab.</p>")
            else:
                self.send_response(400); self.end_headers()
                self.wfile.write(b"auth failed (state mismatch or no code)")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print("Opening Shopify authorization in your browser…")
    print("If it doesn't open, paste this URL:\n  %s" % url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    srv.handle_request()          # serve exactly one request: the OAuth callback
    srv.server_close()
    if "code" not in holder:
        raise AdapterError("no authorization code received (did you approve, and is the redirect URL whitelisted?)")
    return exchange_code(store, client_id, client_secret, holder["code"])
