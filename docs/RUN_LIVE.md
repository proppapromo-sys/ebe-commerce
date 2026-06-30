# Run EBE for real — your shop on autopilot

This is the operator's path: connect your channels, let autopilot keep stock true and
re-buys raised, and glance at `status` to trust it's working. Four steps.

---

## 1. Connect your channels

EBE reads live stock/sales from the channels whose keys are in your `.env`.

```powershell
cd $HOME\ebe-commerce
python -m ebe connections      # see every integration + where to get keys
```

Add the keys to a file named `.env` in the repo root (never commit it — it's git-ignored):

```
# Amazon Selling Partner API
SPAPI_REFRESH_TOKEN=...
SPAPI_CLIENT_ID=...
SPAPI_CLIENT_SECRET=...

# Shopify
SHOPIFY_STORE=your-store
SHOPIFY_TOKEN=shpat_...
```

Then prove the keys actually reach the APIs:

```powershell
python -m ebe check            # ● = live, ○ = not configured
```

> Your seller-SKUs in each channel must match the SKUs in your catalog — that's how EBE
> maps live stock back to your products. Load your catalog with those same SKUs.

---

## 2. Load your catalog (once)

```powershell
python -m ebe catalog --products data\products.csv
```

---

## 3. Turn on autopilot (unattended)

Autopilot does one cycle — **sync** live stock → **raise re-buy drafts** for anything
under its reorder line → (optional) **reprice** — then exits. Schedule it hourly:

```powershell
cd $HOME\ebe-commerce
.\deploy\register-autopilot-task.ps1
```

That registers a Windows Scheduled Task ("EBE Autopilot") that runs every hour and
survives reboots. Each run is logged to `logs\autopilot.log`.

- **Run a cycle right now:** `Start-ScheduledTask -TaskName "EBE Autopilot"`
- **Foreground, watch it live:** `python -m ebe autopilot --every 60`
- **Stop scheduling:** `Unregister-ScheduledTask -TaskName "EBE Autopilot"`

Re-buys land as **drafts** you approve. Only add `--auto` (in `run-autopilot.ps1`) once
you trust a supplier channel to place orders hands-off.

---

## 4. Glance to trust it

```powershell
python -m ebe status
```

```
══ EBE COMMAND · STATUS ══
🟢 AUTOPILOT  12m ago  ·  sync 4/2ch · drafts 1 ($340)
🔌 CHANNELS   ✓amazon, ✓shopify   (2 connected)
📦 CATALOG    4 SKU(s) · 1 under the reorder line
📝 PENDING    1 draft(s) $340 · 0 inbound PO(s) $0
➡️  1 re-buy draft(s) waiting for approval — python -m ebe orders --status draft
```

- 🟢 fresh = ran within the last few hours · 🟡 stale = scheduler may be off · 🔴 never run
- Approve drafts: `python -m ebe orders --status draft`, then `--approve <PO>`
- Receive stock when it lands: `python -m ebe orders --receive <PO>`

That's the whole loop. Connect → schedule → approve drafts. EBE handles the rest.
