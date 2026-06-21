#!/usr/bin/env python3
"""
publish.py — EBE → CHANNEL. The point of having one interface: you manage your catalog
in EBE, run one command, and the products appear on your sales channel. No typing the
same product into Shopify by hand.

Matches by SKU: anything already on the channel (same SKU) is left alone; only the
missing ones are created. Re-running is safe — it never duplicates.

  from ebe.store import Store
  from ebe.adapters.shopify import ShopifyClient
  from ebe.publish import publish_catalog
  publish_catalog(Store("ebe.db"), ShopifyClient())     # creates what's missing
"""
from __future__ import annotations


def publish_catalog(store, client, only=None, set_stock=False) -> dict:
    """Create catalog products that aren't on the channel yet (matched by SKU).

    only        — iterable of SKUs to publish (default: the whole catalog)
    set_stock   — also push on-hand as tracked inventory (needs write_inventory);
                  default False = list untracked (always-available), the no-stock model.
    Returns {created, skipped, failed} lists of SKUs.
    """
    only = set(only) if only else None
    on_channel = {v.get("sku") for v in client.variants() if v.get("sku")}
    created, skipped, failed = [], [], []
    for p in store.products():
        sku = p["sku"]
        if only is not None and sku not in only:
            continue
        if sku in on_channel:
            skipped.append(sku)
            continue
        qty = (p.get("on_hand") or 0) if set_stock else None
        try:
            client.create_product(sku=sku, title=p.get("name") or sku,
                                   price=p.get("sell") or 0,
                                   body_html=p.get("description") or "", qty=qty)
            created.append(sku)
        except Exception as e:
            failed.append((sku, str(e)))
    return {"created": created, "skipped": skipped, "failed": failed}
