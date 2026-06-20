#!/usr/bin/env python3
"""
tenancy.py — MULTI-TENANT CONTROL. The registry behind the hosted EBE: every client
venue is a tenant with its own isolated database, a login, and a subscription the SERVER
checks on every request. Because clients only ever get HTML over HTTP — never the code —
a lapsed subscription is enforced server-side and can't be patched out.

  owner: create_tenant("cloud9", "Cloud9 Lounge", "secret", days=30)
  server: authenticate(id, pw)  ·  is_entitled(id)  → lock if False

Pure stdlib (sqlite3 + hashlib pbkdf2). One control DB lists tenants; each tenant gets
its own ebe data DB so books, stock and customers never bleed across clients.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time

CONTROL_DB = os.environ.get("EBE_CONTROL_DB", "ebe_tenants.db")
TENANT_DIR = os.environ.get("EBE_TENANT_DIR", "tenants")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id       TEXT PRIMARY KEY,
    name     TEXT,
    salt     TEXT NOT NULL,
    pw_hash  TEXT NOT NULL,
    plan     TEXT NOT NULL DEFAULT 'pro',
    status   TEXT NOT NULL DEFAULT 'active',   -- active | suspended
    expires  REAL NOT NULL DEFAULT 0,
    db_path  TEXT NOT NULL,
    created  REAL NOT NULL DEFAULT 0
);
"""


def _hash(password, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()
    return salt, h


class Tenants:
    """The control plane: who's a client, are they paid up, where's their data."""

    def __init__(self, path=CONTROL_DB, tenant_dir=TENANT_DIR):
        self.path = path
        self.tenant_dir = tenant_dir
        os.makedirs(tenant_dir, exist_ok=True)
        self._cx = sqlite3.connect(path)
        self._cx.row_factory = sqlite3.Row
        self._cx.executescript(_SCHEMA)
        self._cx.commit()

    def close(self):
        self._cx.close()

    def create_tenant(self, tid, name, password, days=30, plan="pro"):
        tid = tid.strip().lower()
        salt, h = _hash(password)
        now = time.time()
        db_path = os.path.join(self.tenant_dir, "%s.db" % tid)
        self._cx.execute(
            "INSERT INTO tenants (id,name,salt,pw_hash,plan,status,expires,db_path,created)"
            " VALUES (?,?,?,?,?, 'active', ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET name=excluded.name, plan=excluded.plan",
            (tid, name, salt, h, plan, now + days * 86400, db_path, round(now, 3)))
        self._cx.commit()
        return self.tenant(tid)

    def set_password(self, tid, password):
        salt, h = _hash(password)
        self._cx.execute("UPDATE tenants SET salt=?, pw_hash=? WHERE id=?", (salt, h, tid.lower()))
        self._cx.commit()

    def authenticate(self, tid, password):
        t = self.tenant(tid)
        if not t:
            return False
        _, h = _hash(password, t["salt"])
        return hmac.compare_digest(h, t["pw_hash"])

    def is_entitled(self, tid, now=None):
        """The server's verdict: may this tenant use EBE right now?"""
        now = time.time() if now is None else now
        t = self.tenant(tid)
        return bool(t and t["status"] == "active" and t["expires"] > now)

    def renew(self, tid, days=30):
        """Extend a subscription (called when they pay). Reactivates if suspended."""
        t = self.tenant(tid)
        if not t:
            return None
        base = max(t["expires"], time.time())
        self._cx.execute("UPDATE tenants SET expires=?, status='active' WHERE id=?",
                         (base + days * 86400, tid.lower()))
        self._cx.commit()
        return self.tenant(tid)

    def suspend(self, tid):
        self._cx.execute("UPDATE tenants SET status='suspended' WHERE id=?", (tid.lower(),))
        self._cx.commit()

    def resume(self, tid):
        self._cx.execute("UPDATE tenants SET status='active' WHERE id=?", (tid.lower(),))
        self._cx.commit()

    def tenant(self, tid):
        row = self._cx.execute("SELECT * FROM tenants WHERE id=?", (tid.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def list_tenants(self):
        return [dict(r) for r in self._cx.execute("SELECT * FROM tenants ORDER BY id").fetchall()]

    def status_line(self, tid, now=None):
        now = time.time() if now is None else now
        t = self.tenant(tid)
        if not t:
            return "unknown"
        if t["status"] != "active":
            return "suspended"
        days = (t["expires"] - now) / 86400
        return "active · %.0f days left" % days if days >= 0 else "EXPIRED"
