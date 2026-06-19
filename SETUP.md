# Real-Data Setup — wiring EBE Commerce to live stats

You're starting from zero credentials. This is the order to do it in, fastest win first.
Everything goes into a local **`.env`** file (copy `.env.example` → `.env`; it's git-ignored).
After each step, run `python -m ebe check` to confirm the connection.

> Timeline reality: **Keepa = today.** SP-API ≈ a few hours to a few days (Amazon reviews
> your developer registration). Advertising API ≈ similar, plus an access application.

---

## 1. Keepa — sourcing data (do this first, it's instant)

What it gives you: live buy-box **price** + real **monthly units sold** + category, so the
`sourcing` branch scores your supplier quotes on real numbers.

1. Make an account at **keepa.com**.
2. Go to **keepa.com/#!api** and subscribe to an **API plan** (token-based, paid monthly —
   start on the smallest tier).
3. On that same API page, copy your **API key**.
4. Put it in `.env`:
   ```
   KEEPA_API_KEY=your_key_here
   ```
5. Verify: `python -m ebe check` → should show `● keepa  OK · N tokens left`.
6. Use it: make an `asin,cost` file (see `examples/asin_costs.csv`) with ASINs you're
   considering + your supplier's unit cost, then:
   ```
   python -m ebe sourcing --asin-costs my_asins.csv --fees amazon-fba
   ```

---

## 2. Amazon Selling-Partner API (SP-API) — your listings, prices, FBA stock

Powers the `pricing` and `inventory` branches. Requires a **Professional** seller account.
Good news: since late 2023 there's **no AWS/IAM signing** — just a Login-with-Amazon token.

1. **Seller Central → Settings → Account Info** must show a *Professional* plan.
2. **Seller Central → Apps & Services → Develop Apps** ("Develop Apps for your account").
   - If prompted, complete the **developer profile** (a data-protection questionnaire).
3. Click **Add new app client** → create a **self-authorization** (private) app.
   - Choose the **roles** you need: *Inventory* and *Pricing* (avoid PII/restricted roles).
4. The app gives you a **LWA client ID** and **client secret** →
   ```
   SPAPI_CLIENT_ID=amzn1.application-oa2-client....
   SPAPI_CLIENT_SECRET=...
   ```
5. On the app, click **Authorize** (self-authorization) → it generates a **refresh token**
   for *your own* seller account (no website/redirect needed) →
   ```
   SPAPI_REFRESH_TOKEN=Atzr|...
   ```
6. Set your region/marketplace in `.env` (`SPAPI_REGION=na`, `SPAPI_MARKETPLACE=us`).
7. Verify: `python -m ebe check` → `● amazon  OK · access token acquired`.

> Amazon never knows YOUR cost. Keep a `sku,cost` sheet; the live stock/price gets merged
> with it for true profit-after-fees (cost-merge wiring is the next build step).

---

## 3. Amazon Advertising API — ad spend / sales / ACOS

Powers the `adspend` branch with real campaign performance.

1. You need an active **Amazon Advertising** account (you have one if you run PPC).
2. Create a **Login with Amazon security profile** at **developer.amazon.com**
   (App Console → Security Profiles) → gives a **client ID + secret** →
   ```
   ADS_CLIENT_ID=amzn1.application-oa2-client....
   ADS_CLIENT_SECRET=...
   ```
3. **Apply for Advertising API access** (advertising.amazon.com → API / developer portal).
   Wait for approval.
4. Do the one-time OAuth consent to get a **refresh token** (authorize your ad account,
   exchange the returned code) →
   ```
   ADS_REFRESH_TOKEN=Atzr|...
   ```
5. Get your **profile ID**: with the above set, `python -m ebe check` lists profiles —
   copy the numeric id of your account/marketplace →
   ```
   ADS_PROFILE_ID=1234567890
   ```
6. Verify: `python -m ebe check` → `● amazon-ads  OK · profiles reachable`.

---

## Where each credential is used

| `.env` var | Branch it powers | From |
|---|---|---|
| `KEEPA_API_KEY` | sourcing | keepa.com/#!api |
| `SPAPI_CLIENT_ID/SECRET/REFRESH_TOKEN` | pricing, inventory | Seller Central → Develop Apps |
| `ADS_CLIENT_ID/SECRET/REFRESH_TOKEN/PROFILE_ID` | adspend | developer.amazon.com + Ads API |

## Security

- `.env` is in `.gitignore` — keep it that way. Never commit real keys.
- On a server, prefer real environment variables over a `.env` file.
- These are read-only data pulls; no branch writes to Amazon until you wire live
  execution and pass `live=True` explicitly.

Official docs: SP-API → developer-docs.amazon.com/sp-api · Advertising → advertising.amazon.com/API/docs · Keepa → keepa.com/#!api
