#!/usr/bin/env python3
"""
autopilot.py — THE SELF-RUNNING LOOP. One process that keeps the whole operation
true and moving while you sleep. Each cycle, in order:

    1. SYNC   — pull live on-hand from every configured channel (Amazon/Shopify)
    2. RE-BUY — raise purchase-order drafts for everything under its reorder line
    3. REPRICE— (optional) move prices toward the live market, never below floor

Nothing irreversible happens by default: re-buys land as DRAFTS for you to approve,
and repricing only recommends unless you ask it to commit. Every cycle is logged to
the events table so the dashboard and brief show what the autopilot did and when.

    from ebe.store import Store
    from ebe.autopilot import run
    run(Store("ebe.db"), every_minutes=60)        # forever, one pass an hour
    run(Store("ebe.db"), every_minutes=60, cycles=1)  # one pass, then stop
"""
from __future__ import annotations

import time


def cycle(store, *, prices=False, buy=True, budget=None, auto=False,
          reprice=False, strategy="undercut", floor_roi=0.30, fee=None,
          region="na", marketplace="us") -> dict:
    """Run ONE autopilot pass. Pure orchestration — returns a summary, writes a log."""
    out = {"synced": 0, "channels": 0, "unknown": 0, "drafts": 0, "cash": 0.0,
           "repriced": 0, "errors": []}

    # 1. SYNC — close the loop with what actually sold on each channel
    try:
        from . import sync as syncmod
        chans = syncmod.configured_channels()
        out["channels"] = len(chans)
        if chans:
            res = syncmod.sync_all(store, prices=prices, region=region, marketplace=marketplace)
            for name, r in res.items():
                if "error" in r:
                    out["errors"].append("sync:%s:%s" % (name, r["error"]))
                else:
                    out["synced"] += len(r["updated"])
                    out["unknown"] += len(r["unknown"])
    except Exception as e:                       # a channel hiccup must not stop the loop
        out["errors"].append("sync:%s" % e)

    # 2. RE-BUY — raise drafts (or orders, if auto) for everything under the line
    if buy:
        try:
            from . import autobuy
            raised = autobuy.scan(store, auto=auto, budget=budget)
            out["drafts"] = len(raised)
            out["cash"] = round(sum(po["cash"] for po in raised), 2)
        except Exception as e:
            out["errors"].append("rebuy:%s" % e)

    # 3. REPRICE — only when asked, and only for SKUs carrying an ASIN with live comps
    if reprice:
        try:
            out["repriced"] = _reprice_pass(store, strategy, floor_roi, fee)
        except Exception as e:
            out["errors"].append("reprice:%s" % e)

    note = ("sync %d/%dch · drafts %d ($%.0f) · repriced %d"
            % (out["synced"], out["channels"], out["drafts"], out["cash"], out["repriced"]))
    if out["errors"]:
        note += " · %d error(s)" % len(out["errors"])
    store._log("autopilot", note=note)
    store._cx.commit()
    out["note"] = note
    return out


def _reprice_pass(store, strategy, floor_roi, fee) -> int:
    """Pull live competitor prices (Keepa, by ASIN) and commit recommendations above floor."""
    from . import repricer
    from .adapters.keepa import KeepaClient
    from .fees import AMAZON_FBA
    fee = fee or AMAZON_FBA
    products = store.products()
    prices_by_sku = repricer.live_prices_by_sku(products, KeepaClient().fetch)
    if not prices_by_sku:
        return 0
    recs = repricer.reprice_catalog(products, prices_by_sku, fee,
                                    floor_roi=floor_roi, strategy=strategy)
    moved = 0
    by_sku = {p["sku"]: p for p in products}
    for r in recs:
        if abs(r["move"]) >= 0.01 and r["sku"] in by_sku:
            p = by_sku[r["sku"]]
            store.upsert_products([{**p, "sell": r["recommended"]}])
            moved += 1
    return moved


def run(store, every_minutes=60, cycles=None, on_cycle=None, sleep_fn=time.sleep, **opts) -> list:
    """Loop `cycle` every `every_minutes`. cycles=None runs forever; an int stops after N.

    `on_cycle(n, result)` is called after each pass (the CLI prints with it).
    `sleep_fn` is injectable so tests run without waiting.
    """
    history, n = [], 0
    while cycles is None or n < cycles:
        n += 1
        result = cycle(store, **opts)
        history.append(result)
        if on_cycle:
            on_cycle(n, result)
        if cycles is not None and n >= cycles:
            break
        sleep_fn(max(1, int(every_minutes)) * 60)
    return history
