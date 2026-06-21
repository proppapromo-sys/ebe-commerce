# EBE Command · Shopify Setup (2026)

Your Shopify adapter is built — this wires your store into EBE so stock and prices sync
into the one database alongside Amazon and the venue.

> **What changed:** Shopify **deprecated the old "reveal Admin API token" custom apps on
> Jan 1, 2026.** There is no more `shpat_…` to copy from the admin. Apps now live in the
> **Dev Dashboard** and give a **Client ID + Client Secret**. EBE exchanges those for a
> 24-hour access token automatically (the *client credentials grant*) — no browser, no
> redirect URL, no token to paste. You just provide three values.

---

## 1. Your store handle
The part before `.myshopify.com`. For `g0zjm0-ew.myshopify.com` it's `g0zjm0-ew`.
That's your `SHOPIFY_STORE`.

## 2. Create the app + grab Client ID / Secret
1. Go to the **Dev Dashboard**: https://dev.shopify.com → your org → **Apps** → **Create app**.
2. Give it API scopes (read is all EBE needs): `read_products`, `read_inventory`, `read_orders`.
3. **Install** the app on your store.
4. Open the app → **Settings** → copy **Client ID** and **Client secret**.

> The client credentials grant only works because the app and the store are in **your own
> organization**. That's the normal case for your own shop.

## 3. Put three values in `.env`
The cleanest way (no Notepad, replaces any old/duplicate line):
```powershell
cd $HOME\ebe-commerce
python -c "from ebe.adapters import config; config.set_env('SHOPIFY_STORE','g0zjm0-ew')"
python -c "from ebe.adapters import config; config.set_env('SHOPIFY_CLIENT_ID','PASTE_CLIENT_ID')"
python -c "from ebe.adapters import config; config.set_env('SHOPIFY_CLIENT_SECRET','PASTE_CLIENT_SECRET')"
```
*(An old `SHOPIFY_TOKEN` line, if any, is now ignored — EBE mints fresh tokens itself.)*

## 4. Verify — EBE mints the token for you
```powershell
python -m ebe check          # shopify → ● shop reachable
```
No handshake. EBE calls Shopify's token endpoint with your Client ID + Secret, gets a
24h token, and uses it. It re-mints automatically every run, so the expiry never bites.

## 5. Match SKUs, then sync
- In Shopify, set each **variant SKU** to the same SKU in your catalog. EBE matches on SKU.
```powershell
python -m ebe sync --channel shopify --with-prices   # pulls on-hand + live prices
python -m ebe rebuy                                   # re-buy now runs on Shopify truth too
```

---

### Quick reference
| Field | Where | .env key |
|---|---|---|
| Store handle | before `.myshopify.com` | `SHOPIFY_STORE` |
| Client ID | Dev Dashboard → app → Settings | `SHOPIFY_CLIENT_ID` |
| Client secret | Dev Dashboard → app → Settings | `SHOPIFY_CLIENT_SECRET` |

> Keep `.env` private (it's git-ignored). Never paste the secret in chat or commit it.
> Read-only scopes keep it safe.
