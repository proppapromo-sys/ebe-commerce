# Deploy EBE on Render — always-on, no PC, no tunnel

Goal: EBE live on the web 24/7 at `app.ebehq.com`, running in the cloud (not your PC).
Pure stdlib + one optional AI dependency. ~10 minutes, ~$7/mo (Starter — needed for the
persistent disk that keeps your data between deploys).

---

## 1. Deploy from GitHub
1. Go to **render.com** → sign in with GitHub.
2. **New + → Blueprint** → pick **`proppapromo-sys/ebe-commerce`**.
3. Choose the branch **`claude/funny-carson-iiud2e`** (or merge it to `main` first).
4. Render reads `render.yaml` and proposes the service + a 1 GB disk → **Apply**.

## 2. Set your secrets (Render dashboard → the service → Environment)
- **EBE_OWNER_PASSWORD** → a strong password (this logs you into `/admin`)
- *(optional)* **ANTHROPIC_API_KEY** → turns on the Orb report + AI descriptions
- *(optional, when ready)* your channel keys so the cloud syncs live:
  `SHOPIFY_STORE`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`,
  `SPAPI_CLIENT_ID`, `SPAPI_CLIENT_SECRET`, `SPAPI_REFRESH_TOKEN`, `SPAPI_SELLER_ID`,
  `KEEPA_API_KEY`, `STRIPE_SECRET_KEY`

`EBE_HOST_SECRET` is auto-generated; `EBE_DATA_DIR=/data` and `EBE_BRAND=EBE OS` are preset.

## 3. It's live
Render gives you `https://ebe-XXXX.onrender.com`. Open `/health` → `ok`. Open `/login`.
- Owner sign-in: leave the venue blank (or per host.py) and use **EBE_OWNER_PASSWORD**, or go to **`/admin`**.

## 4. Custom domain → app.ebehq.com
1. Render → service → **Settings → Custom Domains → Add** `app.ebehq.com`.
2. Render shows a CNAME target. In **Cloudflare DNS**, add:
   `CNAME  app  →  <the-target>.onrender.com`  (set **DNS only**, grey cloud, while validating).
3. Render issues HTTPS automatically. Done — `https://app.ebehq.com` is live, always on.

## 5. Load your catalog on the server
The cloud starts with an empty database (your PC's `ebe.db` stays on your PC). Rebuild it
on the server fast:
- Set your **Shopify** keys (step 2) → the server's `sync` pulls your live listings, **or**
- Use the **Catalog** tab to add products / `publish`, **or**
- Re-run your `ebe add` / `import` commands against the hosted instance.

## Rename in 2 weeks
When the marketing platform becomes "Engine", set **`EBE_BRAND=EBE Command`** in Render →
the whole UI re-brands on the next request. No redeploy.

---

### Notes
- **Free tier?** Works for a demo, but it **sleeps after 15 min** and has **no persistent
  disk** (data resets on deploy). For a real business use **Starter** (in `render.yaml`).
- **Always-on autopilot:** add a Render **Cron Job** running `python -m ebe autopilot --cycles 1`
  hourly (same repo, same env) so stock/sales sync + re-buys run in the cloud.
