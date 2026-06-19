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
"""

# columns the catalog importer understands (anything else in a row is ignored)
_PRODUCT_COLS = ("sku", "name", "category", "cost", "sell", "fulfilment",
                 "lead_time_days", "on_hand", "monthly_sales", "supplier")


class Store:
    """A thin, honest wrapper over one SQLite file. Rows come back as plain dicts."""

    def __init__(self, path=DEFAULT_DB):
        self.path = path
        self._cx = sqlite3.connect(path)
        self._cx.row_factory = sqlite3.Row
        self._cx.executescript(_SCHEMA)
        self._cx.commit()

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
