# EBE Command · Amazon Onboarding & Listing Checklist

A practical, do-this-in-order guide to get from "account under review" to **live listings
feeding EBE**. Tailored to your mix: **own-brand merch** (tees/caps) + **resold goods** +
future **private-label hospitality/hookah supplies**.

---

## Phase 0 — Account live (you are here)
- [ ] Professional selling plan active ($39.99/mo) — required for SP-API + bulk listing.
- [ ] Identity / bank / tax verification cleared (the "under review" step).
- [ ] On the brand question you answered **"Some of them"** — keeps both lanes open.

## Phase 1 — Get the 3 API keys (so EBE pulls real stock)
1. Seller Central → **Apps & Services → Develop Apps** → register as a developer.
2. **Add new app client**, request roles: **Inventory**, **Pricing**, **Orders** (read).
   → Amazon gives you `SPAPI_CLIENT_ID` + `SPAPI_CLIENT_SECRET`.
3. **Authorize** the app on your own seller account (self-authorization).
   → Amazon returns `SPAPI_REFRESH_TOKEN`.
4. Put all three in `$HOME\ebe-commerce\.env`, then `python -m ebe check` → Amazon green.

## Phase 2 — Listing your OWN-BRAND merch (no UPCs needed)
You said **No** to UPCs — correct. Instead of buying barcodes, use a **GTIN exemption**:

- [ ] Go to **Catalog → Add Products → "I'm adding a product not sold on Amazon"**.
- [ ] When it asks for a barcode, click **Apply for GTIN exemption**.
- [ ] Pick your category (Clothing) and enter your brand name (**Ebe / Ebe Tech**).
- [ ] Provide proof: a couple of product photos showing **your brand on the product or
      packaging** (a tee with your logo, a cap with the embroidery). No trademark required
      for the exemption itself.
- [ ] Approval is usually minutes-to-a-day. Then you can list each variant (size/color)
      under your own brand with no UPC.

**Listing data to have ready per product** (matches your `data/products.csv`):
`title · brand · category · your price · cost (private) · variations (size/color) · 3–7 photos · bullet points · search terms`

## Phase 3 — Reselling existing products
- [ ] Find the product already on Amazon → **"Sell yours"** → match the existing ASIN.
- [ ] No UPC needed (you attach to the existing listing).
- [ ] Keep your **cost** in `data/costs.csv` so EBE can compute true profit-after-fees.

## Phase 4 — Protect the brand (do this in parallel; unlocks the most upside)
- [ ] File a **trademark** for "Ebe" / "Ebe Tech" (USPTO direct, or **Amazon IP Accelerator**
      for a faster path that grants Brand Registry benefits while the mark is *pending*).
- [ ] Enroll in **Brand Registry** once you have a registered/pending mark. Unlocks:
  - A+ content (richer listings → higher conversion)
  - Listing-hijack protection
  - Sponsored Brands ads + Brand Store
  - Eligibility to **private-label** your hospitality/hookah supplies under your own brand.

## Phase 5 — Wire it into EBE (the payoff)
Once listings are live and the keys work:
```
python -m ebe sync          # pull real on-hand stock from Amazon into the database
python -m ebe rebuy         # auto re-buy on TRUE inventory
python -m ebe po            # supplier order sheets to authorise
python -m ebe brief         # the whole operation in one read
python -m ebe dashboard     # the HUD: Brief · Today · Re-buy · Live Edge · Supply · Venue
```

---

### Quick answers to the setup questions you hit
| Question | Answer | Why |
|---|---|---|
| UPCs for all products? | **No** | Use a free **GTIN exemption** for own-brand merch; match existing ASINs for resale. |
| Diversity certifications? | **No** (unless you hold one) | Optional badge; only if formally certified. |
| Do you own a brand? | **Some of them** | You make own-brand merch **and** resell — keeps GTIN-exemption + Brand Registry open. |

> Rule of thumb: anything that asks "do you own a brand / is this your product" → answer in the
> way that keeps **Brand Registry** and **GTIN exemption** available, because that's what lets
> EBE's private-label engine and protected listings work later.
