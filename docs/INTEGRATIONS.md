# EBE Command · Integrations & Sign-ups

Run `python -m ebe connections` any time to see this live with your configured status.
Put keys in `$HOME\ebe-commerce\.env` (never commit it), then `python -m ebe check`.

---

## ✅ LIVE — adapter built, just add keys

| Integration | What it does for you | Sign up | .env keys |
|---|---|---|---|
| **Anthropic** | The brain — demand calls, AI eyes/ears, daily brief | console.anthropic.com | `ANTHROPIC_API_KEY` |
| **Keepa** | Live price/sales/rank, Product Finder, buy-the-dip arbitrage | keepa.com/#!api | `KEEPA_API_KEY` |
| **Amazon SP-API** | Real listings, stock & prices → the database (`sync`) | sellercentral.amazon.com | `SPAPI_REFRESH_TOKEN` `SPAPI_CLIENT_ID` `SPAPI_CLIENT_SECRET` |
| **Amazon Ads** | Campaign spend/sales → scale winners, cut bleeders | advertising.amazon.com | `ADS_REFRESH_TOKEN` `ADS_CLIENT_ID` `ADS_CLIENT_SECRET` `ADS_PROFILE_ID` |
| **Shopify** | Your own-brand DTC store — stock & price sync | shopify.com | `SHOPIFY_STORE` `SHOPIFY_TOKEN` |
| **Square** | Venue POS — real sales → consumption → auto-reorder | squareup.com/pos | `SQUARE_TOKEN` `SQUARE_LOCATION_ID` |
| **Stripe** ✅ *you're set up* | Real revenue + available balance → the brief & cash forecast | stripe.com | `STRIPE_SECRET_KEY` |

Usage once keyed:
```
python -m ebe sync --channel amazon      # or --channel shopify
python -m ebe venue --square             # pull last 30d of real venue sales
python -m ebe check                      # validate every live key
```

---

## ➕ PLANNED — sign up now, I build the adapter on request

| Integration | Why | Sign up |
|---|---|---|
| **eBay** | Second resale channel for merch & overstock | developer.ebay.com |
| **Etsy** | Handmade / print apparel channel | etsy.com/developers |
| **Walmart Marketplace** | High-volume third channel once Amazon hums | marketplace.walmart.com |
| **TikTok Shop** | Social-commerce for the brand play | seller-us.tiktok.com |
| **Printful** | Print-on-demand — auto-fulfil own-brand apparel, zero inventory risk | printful.com |

---

## The order I'd sign up in (for your business)

1. **Amazon Seller Central** — *in review now.* The anchor channel.
2. **Shopify** — your own-brand storefront. Owns the customer, best margins, no marketplace fees beyond payment.
3. **Square** — you already run the venue; this turns real POS throughput into automatic supply reorders (the hospitality edge).
4. **Printful** — list own-brand merch with **zero inventory risk** while Amazon/Shopify ramp; EBE tracks it as just another supplier.
5. **eBay / Etsy** — cheap extra channels for the same catalog once the first two are humming.
6. **Stripe / QuickBooks** — when you want true cash-in and books wired into the forecast.

> Each marketplace you add multiplies the same catalog across more demand — EBE keeps one
> database of truth and re-buys against total stock, so more channels = more edge, not more chaos.
