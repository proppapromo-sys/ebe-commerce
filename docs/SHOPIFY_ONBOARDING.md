# EBE Command · Shopify Setup

Your Shopify adapter is already built — this is how to wire your store into EBE so stock
and prices sync into the one database, alongside Amazon and the venue.

---

## 0. Pick the plan (honest version)
- The **$1/mo × 3 months** promo is near-zero risk — take it.
- That promo is on the **Advanced** plan ($399/mo after). You only need Advanced for:
  **live 3rd-party shipping rates**, **multi-region storefronts**, the **2.5% card rate**
  (only beats Basic above ~$90k/mo), or **15 staff**.
- If you're starting mostly domestic, **downgrade to Basic ($39) after the trial** — same
  store, same EBE connection. Move up when volume or international demand justifies it.

## 1. Create the store
- Sign up at shopify.com, claim your store handle (e.g. `ebe-tech` → `ebe-tech.myshopify.com`).
- That handle (the part before `.myshopify.com`) is your `SHOPIFY_STORE`.

## 2. Get the Admin API token (this is the key EBE needs)
1. Shopify admin → **Settings → Apps and sales channels → Develop apps**.
2. **Allow custom app development** (one-time), then **Create an app** — name it `EBE`.
3. **Configure Admin API scopes** — grant read access (read is all EBE needs to sync):
   - `read_products`, `read_inventory`, `read_price_rules`, `read_orders`
4. **Install app** → reveal the **Admin API access token** (`shpat_…`). Copy it once.
   - That token is your `SHOPIFY_TOKEN`.

## 3. Put the keys in .env
```
SHOPIFY_STORE=ebe-tech
SHOPIFY_TOKEN=shpat_xxxxxxxxxxxxxxxxxxxxxxxx
```
Then confirm:
```
python -m ebe check        # shopify → ● shop reachable
```

## 4. Match SKUs, then sync
- In Shopify, set each **variant SKU** to the same SKU you use in `data/products.csv`
  (e.g. `M2·OS·Navy`). EBE matches on SKU.
```
python -m ebe sync --channel shopify --with-prices   # pulls on-hand + live prices
python -m ebe rebuy                                   # re-buy now runs on Shopify truth too
```

## 5. What you get inside EBE
- **One database across channels** — Shopify + Amazon stock feed the same auto-reorder and
  vendor auction; no per-channel chaos.
- **Repricer** — `python -m ebe reprice` positions Shopify prices vs the market, floor-protected.
- **Brief & ledger** — Shopify sales flow into the same cash picture (true revenue via Stripe).

---

### Quick reference
| Field | Where | .env key |
|---|---|---|
| Store handle | before `.myshopify.com` | `SHOPIFY_STORE` |
| Admin API token | Develop apps → your app → API credentials | `SHOPIFY_TOKEN` |

> Use the **Admin API token** (`shpat_…`), keep it in `.env` (git-ignored), never paste it in chat
> or commit it. Read-only scopes keep it safe.
