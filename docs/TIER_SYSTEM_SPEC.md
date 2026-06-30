# Subscription / Tier System — Portable Spec

A complete, implementation-agnostic spec of the tiered SaaS subscription model:
plans, features, **settings, team users**, billing lifecycle, and non-payment /
cancellation behavior. Designed so you can re-implement it in another product.

---

## 1. Plans

| Key | Name | Price / month | Team users | Locations | Media storage cap | Positioning |
|------|--------|--------------:|-----------:|----------:|------------------:|-------------|
| `starter` | Starter | $49  | 1  | 1  | 5   | Sales, reviews + self-learning local SEO |
| `growth`  | Growth  | $149 | 3  | 3  | 25  | + social, ads, ROI + KPIs, catering, text club |
| `pro`     | Pro     | $349 | 7  | 7  | 100 | + AI phone, POS sync, 1-click ads, influencers |
| `agency`  | Agency  | $999 | 20 | 20 | 500 | Everything / resell to clients |

- **Order (low→high):** `starter → growth → pro → agency`
- **Team users** = how many people can log into the account (owner + invited staff). *(NEW)*
- **Locations** = how many businesses/locations the account can manage.
- **Media cap** = max saved promo assets (flyers + videos) in the library.
- Tiers are **cumulative**: each tier includes everything below it, plus more.
- Hitting any cap (users, locations, media) triggers an **"Upgrade to add more"** nudge to the
  cheapest plan that raises that cap.

---

## 2. Feature catalogue (capability flags)

| Flag | Description | Starter | Growth | Pro | Agency |
|------|-------------|:--:|:--:|:--:|:--:|
| `local_dashboard`        | Core dashboard (orders, sales, growth plan) | ✓ | ✓ | ✓ | ✓ |
| `review_mgmt`            | Review & reputation management              | ✓ | ✓ | ✓ | ✓ |
| `seo_learning`           | Self-learning local SEO keywords            | ✓ | ✓ | ✓ | ✓ |
| `settings`               | Settings (profile, users, billing, connections) | ✓ | ✓ | ✓ | ✓ |
| `team_users`             | Invite team members (up to seat cap)        | ✓¹| ✓ | ✓ | ✓ |
| `social_content`         | Social content gen + cross-posting          |   | ✓ | ✓ | ✓ |
| `ad_management`          | Ad campaign management (promo push + CAC)   |   | ✓ | ✓ | ✓ |
| `delivery_roi`           | Delivery & ad ROI tracker (true net)        |   | ✓ | ✓ | ✓ |
| `kpi_goals`              | Marketing goals & KPI scoreboard            |   | ✓ | ✓ | ✓ |
| `catering`              | Catering & events pipeline                   |   | ✓ | ✓ | ✓ |
| `pixel_tracking`         | Pixel manager (Meta/Google/TikTok)          |   | ✓ | ✓ | ✓ |
| `loyalty_sms`            | VIP text club (SMS) + automation            |   | ✓ | ✓ | ✓ |
| `influencer_marketplace` | Influencer marketplace + ROI scoring        |   |   | ✓ | ✓ |
| `ai_copy`                | AI-written captions & responses             |   |   | ✓ | ✓ |
| `ai_phone`               | AI phone answering + order capture          |   |   | ✓ | ✓ |
| `pos_sync`               | POS integrations (Toast/Square/Clover)      |   |   | ✓ | ✓ |
| `ad_placement`           | 1-click ad placement (Google/YouTube)       |   |   | ✓ | ✓ |
| `multi_location`         | Multiple locations / accounts               |   |   |   | ✓ |
| `white_label`            | Custom domain + branding (resell)           |   |   |   | ✓ |

¹ Starter has a seat cap of 1 (owner only) — `team_users` is "on" everywhere but the cap gates it.

**Gating helpers the UI needs:**
- `includes(plan, feature)` → bool
- `upgrade_for(feature)` → cheapest plan that unlocks it (for "Upgrade to X" nudges)
- `seat_cap(plan)` / `location_cap(plan)` / `media_cap(plan)` → numeric limits
- `next_seat_upgrade(plan)` / `upgrade_for_storage(plan)` → next plan when a limit is hit

---

## 3. Subscription states

| Status | Entitled? | Meaning |
|--------|:---------:|---------|
| `trialing` | ✅ | In free trial (optional, N days) |
| `active`   | ✅ | Paid and current |
| `past_due` | ❌ | Last payment failed (dunning) — blocked until card fixed |
| `canceled` | ❌ | Subscription ended — blocked until resubscribe |
| `none`     | ❌ | Never subscribed |

**Also entitled (overrides status):**
- **Owner/dev accounts** — listed in `OWNER_TENANTS` config, or `billing.exempt = true` on the profile. Never gated.
- **Comped** — `billing.comp_until` is a future timestamp (e.g. a referral reward grants free access until a date).

Entitlement rule:
```
entitled = is_owner OR status in {active, trialing} OR comp_until > now
```

---

## 4. Lifecycle / state machine

```
                         ┌─────────────────────────────────────────┐
                         ▼                                         │
  signup ──▶ [trialing] ──▶ active ──payment_failed──▶ past_due ──┘ (card fixed → active)
                              │  ▲                          │
                       cancel │  │ payment_recovered        │ stays unpaid / cancels
                              ▼  │                          ▼
                           canceled ◀───────────────────────┘
                   (plan label downgraded to "starter"; status canceled; blocked)
```

### Billing-provider event → state mapping (Stripe model)

| Provider event | Action | New status | Plan change |
|----------------|--------|------------|-------------|
| `checkout.session.completed` | activate | `active` (or `trialing`) | set to purchased plan (from metadata) |
| `customer.subscription.created` / `.updated` | activate/upgrade | provider's status | set to plan from metadata |
| `invoice.payment_failed` | dunning | `past_due` | unchanged |
| `invoice.payment_succeeded` / `invoice.paid` | recover | `active` | unchanged |
| `customer.subscription.deleted` | downgrade | `canceled` | → `starter` (DOWNGRADE_PLAN) |

- Events carry **`metadata.tenant`** (account id) and **`metadata.plan`** so the webhook activates the right account on the right plan.
- Invoice events lack metadata → fall back to matching the stored **Stripe customer / subscription id**.
- **Idempotent:** replaying an event just re-asserts the same state.
- Webhook signatures are **verified** (HMAC-SHA256 of `"<timestamp>.<body>"`, 5-min tolerance).

---

## 5. Non-payment & cancellation behavior (the important part)

**When an account is NOT entitled (`past_due`, `canceled`, `none`):**

1. **All "work" actions are blocked** — sending campaigns, autopilot, email/SMS blasts, posting, ad runs. They hit a paywall explaining why.
2. **Billing + setup stay reachable** so they can recover. Allowed even while unpaid:
   - **GET:** entitlement status, plans, billing account, profile, **settings**, onboarding, tenants, me, referrals, connections, connect-start
   - **POST:** billing checkout, billing portal, login, logout, connect/disconnect, **settings (profile/users)**
   - i.e. *they can pay, manage their card, manage their team, and connect/disconnect accounts — they just can't run the work.*
3. **Dunning email** is sent on `past_due` (failed payment) prompting a card update.
4. **On cancellation:** plan label is **downgraded to `starter`** and status set `canceled` → still blocked until they resubscribe (downgrade is a label/cleanup, not free access).

**Reason strings shown to the user:**
- `past_due` → "Payment failed — update your card to reactivate."
- `canceled` → "Subscription canceled — resubscribe to reactivate."
- `none` → "No active subscription — subscribe to activate the platform."

**Recovery is automatic:** fixing the card fires `invoice.payment_succeeded` → status flips back to `active` → gate reopens. No manual intervention.

---

## 5b. Card capture & recurring-payment structure

How a client adds a card once and gets billed automatically every cycle. **You never see or store
the card number** — Stripe vaults it; you store only opaque ids.

### The three Stripe objects
| Object | What it is | You store |
|--------|-----------|-----------|
| **Customer** | The client; holds the card(s) on file (vaulted) | `billing.customer` (cus_…) |
| **PaymentMethod** | The vaulted card itself (Stripe holds the PAN) | nothing — Stripe owns it |
| **Subscription** | The recurring billing schedule (plan + interval) | `billing.subscription` (sub_…) |

### One-time setup flow (client adds card)
```
1. Client clicks "Subscribe" on a plan
2. App → create Checkout Session (mode=subscription, plan price, metadata{tenant, plan})
3. App redirects client to Stripe's hosted Checkout page
4. Client enters card on Stripe's page  ──►  Stripe creates Customer + vaults card
                                              + creates Subscription (recurring)
5. Stripe redirects back to success_url
6. Webhook `checkout.session.completed` fires → app saves customer id + subscription id,
   sets status = active, plan = purchased plan
```
The card is captured **on Stripe's page**, so your app/servers are out of PCI scope.

### Recurring charges (automatic, every cycle)
```
Each interval (monthly), Stripe auto-charges the card on file:
   success → invoice.payment_succeeded  → status stays/returns to "active"
   failure → invoice.payment_failed     → status "past_due" + dunning email + Stripe auto-retries
```

### Managing the card later (client self-serve)
```
1. Client clicks "Manage billing" (in Settings → Billing)
2. App → create Billing Portal Session for their saved customer id
3. App redirects to Stripe's hosted portal, where the client can:
     • update / replace the card on file
     • view & download invoices
     • change plan (upgrade/downgrade)
     • cancel the subscription
4. Changes flow back as webhooks (subscription.updated / .deleted) → app syncs status & plan
```

### Key rules
- **Capture once, charge forever:** the card is entered a single time at Checkout; Stripe re-uses the vaulted PaymentMethod for every renewal.
- **You store ids, never card data:** only `customer` + `subscription` ids live on the account.
- **The subscription id is the link** between your account record and Stripe's billing schedule.
- **All card edits happen in the hosted portal** — no card form in your app.

---

## 6. Billing mechanics

- **Checkout:** hosted subscription Checkout session per plan. Uses a preconfigured price id (`STRIPE_PRICE_<PLAN>`) if set, else an inline `$X/month` price from `plan.monthly`.
- **Customer portal:** hosted page to update card, view invoices, and cancel.
- **Trial:** optional `trial_period_days` (global `STRIPE_TRIAL_DAYS` or per-checkout).
- **Promo codes:** `allow_promotion_codes = true`; optional fixed `coupon`.
- **Multi-tenant billing:** charges route through the tenant's own Stripe (Connect) with a platform fee — so an agency reselling collects on their own account.
- **Memberships (separate product):** businesses can sell their own VIP membership through the same Stripe wiring, distinguished by `metadata.kind = "membership"` so one webhook handles both without crossing wires.

---

## 7. Reseller / MRR model

For an agency running N accounts across plans `{plan_key: count}`:

```
MRR   = Σ (plan.monthly × count)           # sum across plans
ARR   = MRR × 12
ARPA  = MRR / total_accounts               # average revenue per account

# Forward projection with net growth:
net_monthly_growth = monthly_growth_rate − monthly_churn_rate   # e.g. 0.10 − 0.03 = 0.07
MRR(month_n) = MRR × (1 + net_monthly_growth)^n
```

---

## 8. Config / env keys referenced

| Key | Purpose |
|-----|---------|
| `STRIPE_SECRET_KEY` | enables real billing (else demo mode) |
| `STRIPE_WEBHOOK_SECRET` | verifies webhook signatures |
| `STRIPE_PRICE_<PLAN>` | optional Stripe Price id per plan |
| `STRIPE_TRIAL_DAYS` | optional free-trial length |
| `OWNER_TENANTS` | comma-list of never-gated owner accounts |

---

## 9. Settings  *(NEW)*

Every account has a **Settings** area (always reachable, even when unpaid — see §5). Organized
into sections; each maps to a settings sub-page/tab:

| Section | What the user manages | Notes |
|---------|-----------------------|-------|
| **Business profile** | Name, logo, contact email/phone, address, timezone, currency | Drives branding + receipts |
| **Team & users** | Invite / remove users, assign roles (see §10) | Seat-capped by plan |
| **Plan & billing** | Current plan, usage vs caps, upgrade/downgrade, manage card, invoices | Opens Stripe portal for card/invoices |
| **Connections** | Connect/disconnect channels & integrations (keys, OAuth) | Open even when unpaid |
| **Notifications** | Email/SMS preferences: dunning, alerts, reports, level-up | Per-user + per-account |
| **Branding (white-label)** | Custom domain, logo, colors, "from" email | Agency plan only (`white_label`) |
| **Security** | Password, 2FA, active sessions, API keys | Owner/Admin only |
| **Danger zone** | Cancel subscription, delete account, export data | Owner only; cancel routes to portal |

**Settings API surface (all gated by role, most reachable while unpaid):**
- `GET  /settings` → the whole settings model (profile, team, plan/usage, connections, prefs)
- `POST /settings/profile` → update business profile/branding
- `POST /settings/users/invite` · `/settings/users/remove` · `/settings/users/role`
- `POST /settings/notifications` → update prefs
- `POST /settings/security/*` → password / 2FA / revoke sessions
- Billing actions reuse §5b/§6 (`/billing/checkout`, `/billing/portal`)

---

## 10. Users, roles & seats  *(NEW)*

Different tiers can add more **team users** (the seat cap in §1). Adding a user is the
primary "add users" action.

### Seat caps (from §1)
`starter` = 1 · `growth` = 3 · `pro` = 7 · `agency` = 20.
The **owner counts as a seat.** Inviting beyond the cap is blocked with an upgrade nudge.

### Roles & permissions
| Role | Work actions | Settings | Team mgmt | Billing | Notes |
|------|:--:|:--:|:--:|:--:|------|
| **Owner** | ✓ | ✓ | ✓ | ✓ | One per account; created at signup; only one who can cancel/delete |
| **Admin** | ✓ | ✓ | ✓ | ✗ | Runs the business + manages team, but not billing |
| **Member** | ✓ | partial | ✗ | ✗ | Does the work (catalog, campaigns), can't change account settings |
| **Viewer** | ✗ (read-only) | ✗ | ✗ | ✗ | Sees dashboards/reports only |

### Invite flow
```
1. Owner/Admin → Settings → Team → "Invite user" (email + role)
2. If seats_used >= seat_cap(plan): block → "Upgrade to <next_seat_upgrade> to add more users"
3. Else: create a pending user (status=invited), email an invite link with a signed token
4. Invitee sets a password via the link → user becomes active, consumes a seat
5. Removing a user frees the seat immediately
```

### Helpers the UI needs
- `seat_cap(plan)` → int
- `seats_used(account)` → count of owner + active + invited users
- `can_add_user(account)` → `seats_used < seat_cap(plan)`
- `next_seat_upgrade(plan)` → cheapest plan with a higher seat cap (for the nudge)
- `invite_user(account, email, role)` / `remove_user(account, user_id)` / `set_role(account, user_id, role)`
- `can(user, action)` → permission check against the role matrix

### Auth model
- Sessions are per-**user** (not per-account); a user belongs to exactly one account here
  (an agency manages client accounts via `locations`, not by being a multi-account user).
- Every "work" / settings endpoint checks **both** entitlement (§3) **and** the user's role (§10).

---

### Minimal port checklist for your other software
1. Define the **plans** (price, **users**, locations, caps) + **feature flags** + a tier→feature matrix.
2. Add a per-account **status** field with the 5 states.
3. Implement the **entitlement rule** (owner/exempt OR active/trialing OR comped).
4. Wire **billing webhooks** to the event→state table above (idempotent + signature-verified).
5. Enforce the gate: block "work" endpoints when not entitled; keep **billing + settings** endpoints open.
6. Build the **Settings** area (§9) and **users/roles/seats** (§10); gate every action by entitlement **and** role.
7. Send a **dunning** notice on `past_due`; auto-recover on payment success.
8. On cancel, downgrade plan label and keep blocked until resubscribe.
