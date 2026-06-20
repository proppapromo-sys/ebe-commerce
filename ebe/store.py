#!/usr/bin/env python3
"""
store.py — THE SYSTEM OF RECORD.

Everything EBE knows that must survive a restart lives here, in one SQLite file
(pure standard library, zero dependencies, no signup). This is the database the
auto-rebuy engine reads stock from and writes purchase orders to.

  products         what you sell — cost, price, lead time, ON-HAND stock, demand
  purchase_orders  every reorder the engine raises — status: draft → ordered → received
  events           an append-only log (sales, receipts, decisions) for the record

Lifecycle the rest of the system leans on:
    seed catalog  →  record_sale() drops on_hand  →  autobuy raises a PO
                  →  approve/receive a PO adds the units back  →  loop

  from ebe.store import Store
  s = Store("ebe.db"); s.upsert_products(rows); s.record_sale("M2-Navy", 12)
"""
from __future__ import annotations

import os
import sqlite3
import time

DEFAULT_DB = os.environ.get("EBE_DB", "ebe.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku            TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    category       TEXT,
    cost           REAL NOT NULL DEFAULT 0,
    sell           REAL NOT NULL DEFAULT 0,
    fulfilment     REAL NOT NULL DEFAULT 0,
    lead_time_days INTEGER NOT NULL DEFAULT 21,
    on_hand        INTEGER NOT NULL DEFAULT 0,
    monthly_sales  INTEGER NOT NULL DEFAULT 0,
    supplier       TEXT,
    asin           TEXT,
    updated_at     REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         TEXT NOT NULL,
    name        TEXT,
    qty         INTEGER NOT NULL,
    unit_cost   REAL NOT NULL DEFAULT 0,
    cash        REAL NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'draft',   -- draft | ordered | received | cancelled
    reason      TEXT,
    supplier    TEXT,
    created_at  REAL NOT NULL DEFAULT 0,
    ordered_at  REAL,
    received_at REAL
);
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL DEFAULT 0,
    kind    TEXT NOT NULL,
    sku     TEXT,
    qty     INTEGER,
    note    TEXT
);
CREATE TABLE IF NOT EXISTS suppliers (
    name           TEXT PRIMARY KEY,
    email          TEXT,
    phone          TEXT,
    link           TEXT,
    lead_time_days INTEGER NOT NULL DEFAULT 21,
    min_order      REAL NOT NULL DEFAULT 0,
    notes          TEXT
);
CREATE TABLE IF NOT EXISTS customers (
    name       TEXT PRIMARY KEY,
    email      TEXT,
    phone      TEXT,
    terms_days INTEGER NOT NULL DEFAULT 14,
    notes      TEXT
);
CREATE TABLE IF NOT EXISTS vendor_offers (
    sku            TEXT NOT NULL,
    supplier       TEXT NOT NULL,
    unit_cost      REAL NOT NULL DEFAULT 0,
    lead_time_days INTEGER NOT NULL DEFAULT 21,
    min_qty        INTEGER NOT NULL DEFAULT 1,
    pack_size      INTEGER NOT NULL DEFAULT 1,
    updated_at     REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (sku, supplier)
);
CREATE TABLE IF NOT EXISTS invoices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    party      TEXT,
    kind       TEXT NOT NULL DEFAULT 'AR',       -- AR (they owe you) | AP (you owe them)
    amount     REAL NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'open',      -- open | paid
    due_at     REAL NOT NULL DEFAULT 0,
    ref        TEXT,                              -- e.g. 'sub:3:...' or 'po:12' (idempotency key)
    memo       TEXT,
    created_at REAL NOT NULL DEFAULT 0,
    paid_at    REAL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    sku          TEXT NOT NULL,
    qty          INTEGER NOT NULL DEFAULT 1,
    cadence_days INTEGER NOT NULL DEFAULT 30,
    next_due     REAL NOT NULL DEFAULT 0,
    kind         TEXT NOT NULL DEFAULT 'buy',     -- buy (standing order) | sell (recurring revenue)
    counterparty TEXT,                            -- supplier (buy) or customer (sell)
    unit_price   REAL NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   REAL NOT NULL DEFAULT 0
);
"""

_OFFER_COLS = ("sku", "supplier", "unit_cost", "lead_time_days", "min_qty", "pack_size")
_CUSTOMER_COLS = ("name", "email", "phone", "terms_days", "notes")
_SUB_COLS = ("name", "sku", "qty", "cadence_days", "next_due", "kind", "counterparty", "unit_price")

_SUPPLIER_COLS = ("name", "email", "phone", "link", "lead_time_days", "min_order", "notes")

# columns the catalog importer understands (anything else in a row is ignored)
_PRODUCT_COLS = ("sku", "name", "category", "cost", "sell", "fulfilment",
                 "lead_time_days", "on_hand", "monthly_sales", "supplier", "asin")


class Store:
    """A thin, honest wrapper over one SQLite file. Rows come back as plain dicts."""

    def __init__(self, path=DEFAULT_DB):
        self.path = path
        self._cx = sqlite3.connect(path)
        self._cx.row_factory = sqlite3.Row
        self._cx.executescript(_SCHEMA)
        self._migrate()
        self._cx.commit()

    def _migrate(self):
        """Add columns introduced after a DB was first created (idempotent)."""
        have = {r["name"] for r in self._cx.execute("PRAGMA table_info(products)")}
        for col, decl in (("asin", "TEXT"),):
            if col not in have:
                self._cx.execute("ALTER TABLE products ADD COLUMN %s %s" % (col, decl))

    def close(self):
        self._cx.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- catalog -------------------------------------------------------------
    def upsert_products(self, rows) -> int:
        """Insert or update products by sku. Returns how many rows were written."""
        n = 0
        for raw in rows:
            r = {k: raw.get(k) for k in _PRODUCT_COLS if k in raw}
            sku = (r.get("sku") or "").strip()
            if not sku:
                continue
            r["sku"] = sku
            r.setdefault("name", sku)
            r["updated_at"] = round(time.time(), 3)
            cols = list(r.keys())
            placeholders = ",".join("?" for _ in cols)
            updates = ",".join("%s=excluded.%s" % (c, c) for c in cols if c != "sku")
            self._cx.execute(
                "INSERT INTO products (%s) VALUES (%s) "
                "ON CONFLICT(sku) DO UPDATE SET %s" % (",".join(cols), placeholders, updates),
                [r[c] for c in cols])
            n += 1
        self._cx.commit()
        return n

    def products(self) -> list:
        cur = self._cx.execute("SELECT * FROM products ORDER BY sku")
        return [dict(row) for row in cur.fetchall()]

    def product(self, sku):
        cur = self._cx.execute("SELECT * FROM products WHERE sku=?", (sku,))
        row = cur.fetchone()
        return dict(row) if row else None

    def set_stock(self, sku, on_hand) -> None:
        self._cx.execute("UPDATE products SET on_hand=?, updated_at=? WHERE sku=?",
                         (int(on_hand), round(time.time(), 3), sku))
        self._cx.commit()

    def record_sale(self, sku, units) -> None:
        """A sale drops on_hand (never below zero) and logs the event."""
        units = int(units)
        self._cx.execute(
            "UPDATE products SET on_hand=MAX(0, on_hand-?), updated_at=? WHERE sku=?",
            (units, round(time.time(), 3), sku))
        self._log("sale", sku, -units)
        self._cx.commit()

    # ---- purchase orders -----------------------------------------------------
    def open_skus(self) -> set:
        """SKUs that already have a PO in flight — so we don't double-order."""
        cur = self._cx.execute(
            "SELECT DISTINCT sku FROM purchase_orders WHERE status IN ('draft','ordered')")
        return {row["sku"] for row in cur.fetchall()}

    def create_po(self, sku, qty, unit_cost, reason="", supplier=None, status="draft") -> int:
        qty = int(qty)
        name = (self.product(sku) or {}).get("name", sku)
        cur = self._cx.execute(
            "INSERT INTO purchase_orders (sku,name,qty,unit_cost,cash,status,reason,supplier,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (sku, name, qty, unit_cost, round(qty * unit_cost, 2), status, reason, supplier,
             round(time.time(), 3)))
        self._log("po_" + status, sku, qty, reason)
        self._cx.commit()
        return cur.lastrowid

    def purchase_orders(self, status=None) -> list:
        if status:
            cur = self._cx.execute(
                "SELECT * FROM purchase_orders WHERE status=? ORDER BY created_at DESC", (status,))
        else:
            cur = self._cx.execute(
                "SELECT * FROM purchase_orders ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]

    def mark_ordered(self, po_id) -> None:
        self._cx.execute("UPDATE purchase_orders SET status='ordered', ordered_at=? WHERE id=?",
                         (round(time.time(), 3), po_id))
        self._cx.commit()

    def receive_po(self, po_id) -> dict:
        """Mark a PO received and add its units back into stock. Returns the PO."""
        row = self._cx.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        if not row or row["status"] == "received":
            return dict(row) if row else {}
        po = dict(row)
        self._cx.execute(
            "UPDATE products SET on_hand=on_hand+?, updated_at=? WHERE sku=?",
            (po["qty"], round(time.time(), 3), po["sku"]))
        self._cx.execute("UPDATE purchase_orders SET status='received', received_at=? WHERE id=?",
                         (round(time.time(), 3), po_id))
        self._log("po_received", po["sku"], po["qty"])
        self._cx.commit()
        return self.purchase_order(po_id)

    def cancel_po(self, po_id) -> None:
        self._cx.execute("UPDATE purchase_orders SET status='cancelled' WHERE id=?", (po_id,))
        self._cx.commit()

    def purchase_order(self, po_id):
        row = self._cx.execute("SELECT * FROM purchase_orders WHERE id=?", (po_id,)).fetchone()
        return dict(row) if row else None

    # ---- suppliers -----------------------------------------------------------
    def upsert_suppliers(self, rows) -> int:
        n = 0
        for raw in rows:
            r = {k: raw.get(k) for k in _SUPPLIER_COLS if k in raw}
            name = (r.get("name") or "").strip()
            if not name:
                continue
            r["name"] = name
            cols = list(r.keys())
            ph = ",".join("?" for _ in cols)
            upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c != "name")
            self._cx.execute(
                "INSERT INTO suppliers (%s) VALUES (%s) ON CONFLICT(name) DO UPDATE SET %s"
                % (",".join(cols), ph, upd), [r[c] for c in cols])
            n += 1
        self._cx.commit()
        return n

    def suppliers(self) -> list:
        cur = self._cx.execute("SELECT * FROM suppliers ORDER BY name")
        return [dict(row) for row in cur.fetchall()]

    def supplier(self, name):
        if not name:
            return None
        row = self._cx.execute("SELECT * FROM suppliers WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    # ---- customers -----------------------------------------------------------
    def upsert_customers(self, rows) -> int:
        n = 0
        for raw in rows:
            r = {k: raw.get(k) for k in _CUSTOMER_COLS if k in raw}
            name = (r.get("name") or "").strip()
            if not name:
                continue
            r["name"] = name
            cols = list(r.keys())
            ph = ",".join("?" for _ in cols)
            upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c != "name")
            self._cx.execute(
                "INSERT INTO customers (%s) VALUES (%s) ON CONFLICT(name) DO UPDATE SET %s"
                % (",".join(cols), ph, upd), [r[c] for c in cols])
            n += 1
        self._cx.commit()
        return n

    def customers(self) -> list:
        return [dict(r) for r in self._cx.execute("SELECT * FROM customers ORDER BY name").fetchall()]

    def customer(self, name):
        if not name:
            return None
        row = self._cx.execute("SELECT * FROM customers WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None

    # ---- vendor bidding ------------------------------------------------------
    def upsert_offers(self, rows) -> int:
        """Insert/update vendor offers keyed by (sku, supplier). Returns rows written."""
        n = 0
        for raw in rows:
            r = {k: raw.get(k) for k in _OFFER_COLS if k in raw}
            sku, sup = (r.get("sku") or "").strip(), (r.get("supplier") or "").strip()
            if not sku or not sup:
                continue
            r["sku"], r["supplier"] = sku, sup
            r["updated_at"] = round(time.time(), 3)
            cols = list(r.keys())
            ph = ",".join("?" for _ in cols)
            upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c not in ("sku", "supplier"))
            self._cx.execute(
                "INSERT INTO vendor_offers (%s) VALUES (%s) ON CONFLICT(sku,supplier) DO UPDATE SET %s"
                % (",".join(cols), ph, upd), [r[c] for c in cols])
            n += 1
        self._cx.commit()
        return n

    def offers_for(self, sku) -> list:
        cur = self._cx.execute("SELECT * FROM vendor_offers WHERE sku=? ORDER BY unit_cost", (sku,))
        return [dict(row) for row in cur.fetchall()]

    def best_offer(self, sku, qty=None):
        """The winning bid for a SKU: cheapest unit cost meeting min_qty, lead time as tie-break."""
        offers = self.offers_for(sku)
        eligible = [o for o in offers if qty is None or qty >= (o.get("min_qty") or 1)]
        pool = eligible or offers
        if not pool:
            return None
        return min(pool, key=lambda o: (o.get("unit_cost") or 0, o.get("lead_time_days") or 0))

    # ---- ledger (accounts receivable / payable) ------------------------------
    def create_invoice(self, party, amount, kind="AR", due_days=14, ref=None, memo=None):
        """Open an invoice. If `ref` is given and already exists, do nothing (idempotent)."""
        if ref and self.invoice_by_ref(ref):
            return None
        now = time.time()
        cur = self._cx.execute(
            "INSERT INTO invoices (party,kind,amount,status,due_at,ref,memo,created_at)"
            " VALUES (?,?,?,'open',?,?,?,?)",
            (party, kind, round(float(amount), 2), now + due_days * 86400, ref, memo, round(now, 3)))
        self._cx.commit()
        return cur.lastrowid

    def invoice_by_ref(self, ref):
        row = self._cx.execute("SELECT * FROM invoices WHERE ref=?", (ref,)).fetchone()
        return dict(row) if row else None

    def invoices(self, status=None, kind=None) -> list:
        q, params = "SELECT * FROM invoices", []
        where = []
        if status:
            where.append("status=?"); params.append(status)
        if kind:
            where.append("kind=?"); params.append(kind)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY due_at"
        return [dict(r) for r in self._cx.execute(q, params).fetchall()]

    def mark_invoice_paid(self, inv_id) -> None:
        self._cx.execute("UPDATE invoices SET status='paid', paid_at=? WHERE id=?",
                         (round(time.time(), 3), inv_id))
        self._cx.commit()

    # ---- subscriptions / standing orders -------------------------------------
    def add_subscription(self, sku, qty, cadence_days, kind="buy", counterparty=None,
                         unit_price=0.0, next_due=None, name=None) -> int:
        now = time.time()
        cur = self._cx.execute(
            "INSERT INTO subscriptions (name,sku,qty,cadence_days,next_due,kind,counterparty,unit_price,active,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,1,?)",
            (name or sku, sku, int(qty), int(cadence_days),
             float(next_due if next_due is not None else now), kind, counterparty,
             float(unit_price), round(now, 3)))
        self._cx.commit()
        return cur.lastrowid

    def subscriptions(self, active_only=True) -> list:
        q = "SELECT * FROM subscriptions" + (" WHERE active=1" if active_only else "") + " ORDER BY next_due"
        return [dict(r) for r in self._cx.execute(q).fetchall()]

    def due_subscriptions(self, as_of=None) -> list:
        as_of = time.time() if as_of is None else as_of
        cur = self._cx.execute(
            "SELECT * FROM subscriptions WHERE active=1 AND next_due<=? ORDER BY next_due", (as_of,))
        return [dict(r) for r in cur.fetchall()]

    def advance_subscription(self, sub_id, as_of=None) -> None:
        """Roll a fulfilled subscription forward by its cadence."""
        row = self._cx.execute("SELECT cadence_days FROM subscriptions WHERE id=?", (sub_id,)).fetchone()
        if not row:
            return
        base = time.time() if as_of is None else as_of
        self._cx.execute("UPDATE subscriptions SET next_due=? WHERE id=?",
                         (base + row["cadence_days"] * 86400, sub_id))
        self._cx.commit()

    def cancel_subscription(self, sub_id) -> None:
        self._cx.execute("UPDATE subscriptions SET active=0 WHERE id=?", (sub_id,))
        self._cx.commit()

    def record_sales(self, counts) -> int:
        """Bulk record sales from a {sku: units} mapping. Returns SKUs touched."""
        n = 0
        for sku, units in dict(counts).items():
            if self.product(sku):
                self.record_sale(sku, units)
                n += 1
        return n

    # ---- events --------------------------------------------------------------
    def _log(self, kind, sku=None, qty=None, note=None) -> None:
        self._cx.execute("INSERT INTO events (ts,kind,sku,qty,note) VALUES (?,?,?,?,?)",
                         (round(time.time(), 3), kind, sku, qty, note))

    def events(self, limit=100) -> list:
        cur = self._cx.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]


def product_as_item(p: dict) -> dict:
    """Shape a stored product row like the items the genome branches expect."""
    return {
        "id": p["sku"], "sku": p["sku"], "name": p["name"], "category": p.get("category"),
        "cost": p.get("cost", 0), "sell": p.get("sell", 0),
        "fulfilment": p.get("fulfilment", 0), "lead_time_days": p.get("lead_time_days", 21),
        "on_hand": p.get("on_hand", 0), "monthly_sales": p.get("monthly_sales", 0),
        "supplier": p.get("supplier"),
    }
