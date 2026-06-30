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

_DATA = os.environ.get("EBE_DATA_DIR", "")     # persistent disk dir (Render etc.); "" = cwd
CONTROL_DB = os.environ.get("EBE_CONTROL_DB") or os.path.join(_DATA, "ebe_tenants.db")
TENANT_DIR = os.environ.get("EBE_TENANT_DIR") or os.path.join(_DATA, "tenants")

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
    stripe_customer TEXT,
    created  REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tenant_users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant       TEXT NOT NULL,
    email        TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT 'member',     -- owner | admin | member | viewer
    status       TEXT NOT NULL DEFAULT 'invited',    -- invited | active
    salt         TEXT,
    pw_hash      TEXT,
    invite_token TEXT,
    created      REAL NOT NULL DEFAULT 0,
    UNIQUE(tenant, email)
);
"""

ROLES = ("owner", "admin", "member", "viewer")


class SeatLimitError(Exception):
    """Raised when inviting a user would exceed the plan's seat cap."""


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
        have = {r["name"] for r in self._cx.execute("PRAGMA table_info(tenants)")}
        if "stripe_customer" not in have:                # migrate older control DBs
            self._cx.execute("ALTER TABLE tenants ADD COLUMN stripe_customer TEXT")
        ucols = {r["name"] for r in self._cx.execute("PRAGMA table_info(tenant_users)")}
        if ucols and "invite_token" not in ucols:        # migrate older team tables
            self._cx.execute("ALTER TABLE tenant_users ADD COLUMN invite_token TEXT")
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

    # ---- team users (seats) --------------------------------------------------
    def seat_cap(self, tid):
        """Max users (incl. owner) the tenant's plan allows."""
        from . import plans
        t = self.tenant(tid)
        return plans.seat_cap(t["plan"]) if t else 1

    def list_users(self, tid):
        cur = self._cx.execute(
            "SELECT id,email,role,status,invite_token,created FROM tenant_users "
            "WHERE tenant=? ORDER BY id", (tid.lower(),))
        return [dict(r) for r in cur.fetchall()]

    def get_user(self, tid, email):
        row = self._cx.execute(
            "SELECT * FROM tenant_users WHERE tenant=? AND email=?",
            (tid.lower(), email.strip().lower())).fetchone()
        return dict(row) if row else None

    def seats_used(self, tid):
        """Owner counts as 1, plus every invited/active team user."""
        n = self._cx.execute("SELECT COUNT(*) FROM tenant_users WHERE tenant=?",
                             (tid.lower(),)).fetchone()[0]
        return 1 + int(n)

    def can_add_user(self, tid):
        return self.seats_used(tid) < self.seat_cap(tid)

    def add_user(self, tid, email, role="member"):
        """Invite a team user. Returns a one-time invite token to share (the user sets
        their own password via accept_invite). Raises SeatLimitError at the seat cap.
        Re-inviting an existing teammate reissues their token without taking a new seat."""
        tid = tid.lower()
        email = email.strip().lower()
        role = role if role in ROLES else "member"
        if not self.get_user(tid, email) and not self.can_add_user(tid):
            raise SeatLimitError("seat limit reached for plan")
        token = os.urandom(16).hex()
        self._cx.execute(
            "INSERT INTO tenant_users (tenant,email,role,status,invite_token,created) "
            "VALUES (?,?,?, 'invited', ?, ?) "
            "ON CONFLICT(tenant,email) DO UPDATE SET role=excluded.role, "
            "invite_token=excluded.invite_token, status='invited'",
            (tid, email, role, token, round(time.time(), 3)))
        self._cx.commit()
        return token

    def accept_invite(self, tid, token, password):
        """Redeem an invite token: set the user's password and activate them.
        Returns the user dict on success, or None for a bad/expired token."""
        if not token:
            return None
        row = self._cx.execute(
            "SELECT id FROM tenant_users WHERE tenant=? AND invite_token=?",
            (tid.lower(), token)).fetchone()
        if not row:
            return None
        salt, h = _hash(password)
        self._cx.execute(
            "UPDATE tenant_users SET salt=?, pw_hash=?, status='active', invite_token=NULL "
            "WHERE id=?", (salt, h, row["id"]))
        self._cx.commit()
        return dict(self._cx.execute(
            "SELECT * FROM tenant_users WHERE id=?", (row["id"],)).fetchone())

    def authenticate_user(self, tid, email, password):
        """Verify a team user's login. Returns the user dict (with role) or None."""
        u = self.get_user(tid, email)
        if not u or u["status"] != "active" or not u["pw_hash"]:
            return None
        _, h = _hash(password, u["salt"])
        return u if hmac.compare_digest(h, u["pw_hash"]) else None

    def user_role(self, tid, email):
        """Role for a team member, or None if not a user of this tenant."""
        u = self.get_user(tid, email)
        return u["role"] if u else None

    def set_role(self, tid, uid, role):
        if role not in ROLES:
            return
        self._cx.execute("UPDATE tenant_users SET role=? WHERE tenant=? AND id=?",
                         (role, tid.lower(), int(uid)))
        self._cx.commit()

    def remove_user(self, tid, uid):
        self._cx.execute("DELETE FROM tenant_users WHERE tenant=? AND id=?",
                         (tid.lower(), int(uid)))
        self._cx.commit()

    def suspend(self, tid):
        self._cx.execute("UPDATE tenants SET status='suspended' WHERE id=?", (tid.lower(),))
        self._cx.commit()

    def resume(self, tid):
        self._cx.execute("UPDATE tenants SET status='active' WHERE id=?", (tid.lower(),))
        self._cx.commit()

    def link_stripe(self, tid, customer_id):
        self._cx.execute("UPDATE tenants SET stripe_customer=? WHERE id=?", (customer_id, tid.lower()))
        self._cx.commit()

    def tenant(self, tid):
        row = self._cx.execute("SELECT * FROM tenants WHERE id=?", (tid.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def tenant_by_stripe(self, customer_id):
        if not customer_id:
            return None
        row = self._cx.execute("SELECT * FROM tenants WHERE stripe_customer=?", (customer_id,)).fetchone()
        return dict(row) if row else None

    def exists(self, tid):
        return self.tenant(tid) is not None

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
