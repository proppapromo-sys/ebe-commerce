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

import re


def _plain(text):
    """Strip HTML to plain text — Amazon descriptions want no markup."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def amazon_attributes(product, marketplace_id):
    """A baseline Listings-Items attribute set from a catalog product.
    Covers the commonly-required fields; some Amazon categories need more."""
    mp = marketplace_id
    price = float(product.get("sell") or 0)
    qty = int(product.get("on_hand") or 0)
    title = product.get("name") or product["sku"]
    brand = (product.get("brand") or product.get("supplier") or "Generic")
    desc = _plain(product.get("description")) or title
    return {
        "condition_type": [{"value": "new_new", "marketplace_id": mp}],
        "item_name": [{"value": title[:200], "marketplace_id": mp}],
        "brand": [{"value": brand, "marketplace_id": mp}],
        "manufacturer": [{"value": brand, "marketplace_id": mp}],
        "product_description": [{"value": desc[:2000], "marketplace_id": mp}],
        "fulfillment_availability": [{"fulfillment_channel_code": "DEFAULT", "quantity": qty}],
        "purchasable_offer": [{
            "marketplace_id": mp, "currency": "USD",
            "our_price": [{"schedule": [{"value_with_tax": price}]}],
        }],
    }


def publish_to_amazon(store, client, seller_id, product_type, marketplace_id, only=None) -> dict:
    """Create/replace catalog listings on Amazon (Listings Items API). PUT is upsert —
    re-running updates. Returns {created, failed}. Amazon validates strictly per product type."""
    only = set(only) if only else None
    created, failed = [], []
    for p in store.products():
        sku = p["sku"]
        if only is not None and sku not in only:
            continue
        attrs = amazon_attributes(p, marketplace_id)
        try:
            client.put_listing(seller_id, sku, product_type, attrs)
            created.append(sku)
        except Exception as e:
            failed.append((sku, str(e)))
    return {"created": created, "failed": failed}


def publish_catalog(store, client, only=None, set_stock=False, update=False) -> dict:
    """Push the catalog to the channel (matched by SKU).

    only        — iterable of SKUs to publish (default: the whole catalog)
    set_stock   — also push on-hand as tracked inventory (needs write_inventory);
                  default False = list untracked (always-available), the no-stock model.
    update      — also UPDATE listings already on the channel (title/description/price/
                  photo) instead of skipping them. Default False = create-only.
    Returns {created, updated, skipped, failed}.
    """
    only = set(only) if only else None
    on_channel = {v.get("sku") for v in client.variants() if v.get("sku")}
    created, updated, skipped, failed = [], [], [], []
    for p in store.products():
        sku = p["sku"]
        if only is not None and sku not in only:
            continue
        title = p.get("name") or sku
        body = p.get("description") or ""
        image = p.get("image_url") or None
        if sku in on_channel:
            if not update:
                skipped.append(sku)
                continue
            try:
                client.update_product(sku=sku, title=title, price=p.get("sell") or 0,
                                      body_html=body, image_url=image)
                updated.append(sku)
            except Exception as e:
                failed.append((sku, str(e)))
            continue
        qty = (p.get("on_hand") or 0) if set_stock else None
        try:
            client.create_product(sku=sku, title=title, price=p.get("sell") or 0,
                                   body_html=body, qty=qty, image_url=image)
            created.append(sku)
        except Exception as e:
            failed.append((sku, str(e)))
    return {"created": created, "updated": updated, "skipped": skipped, "failed": failed}
