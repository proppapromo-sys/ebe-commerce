# EBE Command

A **risk-first operator brain** — built to maximise *profit after every fee*, not vanity
revenue, and to read a market through *your* lens. One **Universal Genome** (a reusable
decision skeleton), many **branches** you snap on. It scouts opportunities, sources, prices,
restocks, runs ads, plugs return leaks, tracks your own venue's supplies — all personalised to
the operator. The architecture grows toward a full operator + supply platform.

> Philosophy: **survive first, edge second.** No edge → no action. Prove it with a small
> test before you scale. Every number is taken *after* the marketplace's vig.

---

## The branches (run any of them today)

Each branch is the **same loop** with different cells. Pure standard library — no installs.

```bash
python -m ebe sourcing      # which products to SOURCE (ROI after every fee, test-batch first)
python -m ebe pricing       # REPRICE each SKU to its max profit-after-fees price
python -m ebe inventory     # RESTOCK before you stock out (per size/colour for apparel)
python -m ebe adspend       # SCALE ad winners, CUT the bleeders
python -m ebe all --place   # run every branch once and emit the (dry-run) actions

# pick a fee model:
python -m ebe sourcing --fees amazon-apparel   # higher referral + brutal return rate
#   choices: amazon-fba (default) · amazon-apparel · shopify · etsy
```

`--place` hands cleared decisions to the execution organ (always **dry-run** until you wire
in real APIs and pass `live=True`).

### Run it on YOUR data (CSV)

No code edits — export your catalog / inventory / ad campaigns to CSV and load them in:

```bash
python -m ebe all      --products examples/products.csv --campaigns examples/campaigns.csv
python -m ebe sourcing --products my_catalog.csv --fees amazon-apparel
python -m ebe adspend  --campaigns my_ads.csv
```

**`products.csv`** — one row per SKU; apparel repeats the product columns, one row per
size/colour variant (see [`examples/products.csv`](examples/products.csv)):

```
id,name,category,cost,sell,fulfilment,competition,lead_time_days,elasticity,size,color,on_hand,monthly_sales
P1,LED strip lights,home,5,22,4,0.4,18,1.8,,,900,800
M1,Graphic tee,apparel,9,28,5,0.5,21,1.6,S,Black,15,40
M1,Graphic tee,apparel,9,28,5,0.5,21,1.6,M,Black,60,120
```

**`campaigns.csv`** — one row per advertised SKU (see [`examples/campaigns.csv`](examples/campaigns.csv)):

```
id,name,category,sell,cost,spend,ad_sales,target_acos
C-P1,LED strips,home,22,5,600,4200,0.25
```

### Run it on LIVE data (real APIs)

Connect to the real systems your numbers live in. Credentials go in a git-ignored `.env`
(`cp .env.example .env`); **[SETUP.md](SETUP.md)** is the step-by-step to obtain each one.

```bash
python -m ebe check     # doctor: which integrations are wired + reachable
```

| Integration | Powers | Status | Get a key |
|---|---|---|---|
| **Keepa** | sourcing (live price + real monthly sales) | ✅ usable today | instant — keepa.com/#!api |
| **Amazon SP-API** | pricing, inventory (your listings/stock) | auth wired, comes online with creds | Seller Central → Develop Apps |
| **Amazon Ads API** | adspend (real spend/sales/ACOS) | auth wired, comes online with creds | developer.amazon.com |

Live sourcing today (Keepa key + an `asin,cost` sheet of supplier quotes):

```bash
python -m ebe sourcing --asin-costs examples/asin_costs.csv --fees amazon-fba
```

### Discover — let the engine *find* products for you

`discover` queries Keepa's Product Finder by your filters, pulls back a ranked shortlist of
real ASINs (high demand, low competition, in your price band), and scores each after fees:

```bash
python -m ebe discover --category home --min-sales 300 --max-price 50 --max-sellers 8
```

Discovery finds candidates; it can't know your **cost**, so it assumes a labelled
`--cost-ratio` (default 35% of sell price) just to rank them. The flow: *engine surfaces
20 candidates → you get real supplier quotes for the few that clear → re-run `sourcing
--asin-costs` with the true cost.* Categories: home, kitchen, health, beauty, sports,
toys, pet, office, garden, baby, electronics, apparel.

### AI brain (Claude, caged by the genome)

The `--ai` flag puts **Claude (`claude-opus-4-8`)** in the BRAIN organ: it estimates a
product's real demand and *how sure it is*, and `edge = ROI-after-fees × confidence` —
so an unsure AI can't talk the engine into a buy. Claude's demand read feeds the Heart's
sizing, but the **caps, the kill-switch and the test-batch stay in plain code**. The Brain
proposes; the Heart disposes. (See "The vision" below.)

```bash
pip install anthropic          # optional dependency, only for --ai
# ANTHROPIC_API_KEY=... in .env
python -m ebe sourcing --ai --fees amazon-apparel
```

### The vision: AI *in* the genome, never *driving* it

AI lives inside specific organs and is bounded by the five laws — never given the wheel:

| Organ | AI's job | AI-free? |
|---|---|---|
| 👂 Ears | normalize messy supplier data | — |
| 🧠 Brain | estimate demand / fair value → `mine()` | the edge gate stays code |
| ❤️ Heart | **none** — sizing, caps, kill-switch | ✅ **by design** |
| ✋ Hands | listing/ad copy | the action stays confirm-first |
| 👁️ Eyes | recognize products / trends | a pattern graduates only on proof |
| 🩸 TruthMeter | **none** — measures real sell-through | ✅ **keeps AI honest** |

Shipped today: the **AI Brain**. Next: AI Eyes (trend/product recognition) and Ears
(supplier-data normalization), on `claude-haiku-4-5` for cheap high volume.

| Branch | Question it answers | Edge = |
|---|---|---|
| `sourcing` | What should I buy in? | ROI after all fees vs break-even |
| `pricing` | What price makes the most money? | profit uplift vs today's price |
| `inventory` | What's about to stock out? | how far below the reorder point |
| `adspend` | Where should ad money go? | headroom under target ACOS |
| `returns` | Which SKUs leak margin to returns? | return rate above the category norm |

---

## Why "profit after fees" is the whole game

The trap most sellers fall into is reading gross margin. `ebe/fees.py` makes the vig explicit:

```
$30 item costing $8:
  amazon-fba       net $7.50    ROI  94%   margin 25%   breakeven-ROAS 2.50
  amazon-apparel   net $1.40    ROI  17%   margin  5%   breakeven-ROAS 5.08   ← clothes hurt
  shopify          net $8.23    ROI 103%   margin 27%   breakeven-ROAS 2.11
  etsy             net $11.45   ROI 143%   margin 38%   breakeven-ROAS 1.99
```

Apparel pays a higher referral fee **and** a 15–25% return rate (people order three sizes,
keep one). `MERCH_APPAREL` bakes that in, so the engine never fools itself on your clothing.

---

## The Universal Genome (seven organs)

Every branch implements the same skeleton in [`ebe/genome.py`](ebe/genome.py):

| Organ | Role |
|---|---|
| 👂 `DataFeed` | EARS — the things you could act on right now |
| 🧠 `EdgeModel` | BRAIN — *your* number vs the world's number → the edge |
| ❤️ `Risk` | HEART — **built first**; sizing, caps, kill-switch, veto |
| ✋ `Execution` | HANDS — confirm-first; dry-run unless `live=True` |
| 👁️ `Eyes` | recognise + remember patterns; vote only once *proven* |
| 🩸 `TruthMeter` | fast forward-validation (real sell-through / CLV) |
| 🔄 `Machine` | wires them into one loop: `.cycle()` or `.run_forever()` |

**The five laws (the DNA):** risk-first · edge = you vs the world · forward-validate before
real stakes · recognise+remember don't predict · confirm-first, never chase.

### Genome v2 — the loop actually learns and guards itself

```bash
python -m ebe sourcing --journal record.jsonl   # write every decision (the record, law 4)
python -m ebe all --budget 1000                  # cap TOTAL $ committed across all branches
python -m ebe discover --category home --max-calls 50   # cap outbound API spend this run
```

- **Journal + LearningEyes** — decisions and outcomes are recorded; `pattern_trust()` turns
  the record into trust, so patterns *graduate on evidence* (~3 clean wins) instead of sitting
  inert. Laws 3 & 4, made real.
- **Sanity gate** — impossible rows (cost ≤ 0, negatives, non-finite) are dropped at the Ears
  before the Brain ever sees them.
- **Portfolio cap** — one shared exposure ledger so clearing many SKUs can't over-commit.
- **Retry + budget guards** — adapters retry transient API errors (429/5xx, `Retry-After`) and
  honour a per-run call budget so live runs can't burn unlimited Keepa tokens / Anthropic spend.

### Grow a new branch

```python
from ebe.genome import EdgeModel, Risk, Execution, BlindEyes, Machine

class MyEdge(EdgeModel):
    def fair(self, x): ...      # the world's number
    def mine(self, x): ...      # your number

class MyRisk(Risk):
    def kelly(self, x, edge): return edge

class MyHands(Execution):
    def place(self, x, stake, live=False): ...

Machine(my_feed, MyEdge(), MyRisk(bankroll=2000), BlindEyes(), MyHands()).cycle(place=True)
```

---

## Scout the landscape — personalised to you

The engine isn't one strategy; it's a lens on the whole market, tuned to *you*. A **Profile**
captures your capital, risk appetite, focus categories, and real-world advantages; **`scout`**
then surveys a market through that lens — ranking opportunities and reading each lane (open vs
leaders-dominate) so two operators get *different* shortlists from identical data.

```bash
python -m ebe scout --profile hookah        # hookah/bar/takeout advantages weight the results
python -m ebe scout --profile generic
```

Profiles live in `ebe/profile.py` (`hookah`, `generic`, `cautious`, `aggressive`) — clone and
tune one to a real operator. Feed it `discover` output to scout a live market.

### True edge — every angle, fused

Profit is one angle; a *defensible* position stacks many. `edges` scores **seven independent
edge angles** — margin, demand, open-lane, your advantage, recurrence (re-buy moat), timing,
arbitrage — fuses them (weighted by your goals), and flags what you can actually **corner**
(defensible *and* profitable), not just what's momentarily profitable.

```bash
python -m ebe edges --profile hookah
```
```
  product                       mrg dmd cmp adv rec tim arb | EDGE moat  verdict
  Disposable hookah mouth tips 100  60  70 100 100  50  50 |  84%  90%  CORNER
  Vegetable chopper            100 100  10   0  30  50  50 |  56%  13%  TEST   ← high profit, no moat
```

High margin with a thin moat is a treadmill; the engine steers you to the lanes you can own.

Run it on **live** ASINs and the engine fuses real data on every angle — margin/demand/
competition from Keepa, **live arbitrage** (price dip), and **live timing** (sales-rank momentum:
rising vs fading):

```bash
python -m ebe edges --asins "B08VRZTHDL,B0BTD83JZR" --profile hookah --cost-ratio 0.35
```

### Live arbitrage — buy low, sell high (real Keepa data)

`arbitrage` reads each ASIN's price against its own **90-day average and low** and flags what's
trading cheap *right now* — the moment to source/stock before the recovery. Temporal arbitrage
runs live today on your Keepa key; cross-channel (Amazon vs Walmart/eBay/Shopify) snaps in by
adding a `PriceSource` (`ebe/arbitrage.py`). The score feeds the `arb` angle of the true-edge engine.

```bash
python -m ebe arbitrage --asins "B08VRZTHDL,B0BTD83JZR,B09XDTKZ8J"
```
```
  ASIN        product            now    avg    low   dip  spread  edge  signal
  B0BTD83JZR  Karat clamshell   $38.10 $45.14 $37.20  16%   30%   72%  BUY THE DIP
```

## Venue supply tracking — the same genome, pointed at your own venue

Another lane: run the engine on your *own* consumption. It takes your POS counts (drinks /
hookahs / takeout), explodes each sale's bill-of-materials into the supplies it consumed, and
runs the **same restock brain** the Amazon inventory branch uses to say *"you'll run out of
charcoal in 19 days — reorder?"*

```bash
python -m ebe venue
python -m ebe venue --sales "drink=500,hookah=120,takeout=85" --period 30
```
```
consumption from: 500 drinks · 120 hookahs · 85 takeout
  Coconut charcoal cube     480 used/mo · 19d cover · $29/mo
  3-compartment container    85 used/mo · 14d cover · $20/mo
  ...
  monthly supply spend ≈ $130
⚠️  Running low → reorder?
  🛒 REORDER Coconut charcoal cube   1000 units (1 × 1000-pack) · $60 · cover 19d  [one-click ✅]
```

Define your menu's recipes in `ebe/venue/sample.py`. This is Phase 1 (track your own venue);
it grows into auto-reordering, waste/shrinkage detection, supply sales, and multi-venue.

---

## Layout

```
ebe/
  genome.py            # the Universal Genome skeleton (the five laws + Machine loop)
  fees.py              # marketplace fee models: amazon-fba, amazon-apparel, shopify, etsy
  catalog/
    product.py         # Product + Variant (size × colour stock for merch/apparel)
    feeds.py           # sample generic + apparel/merch catalogs (swap for your data)
  branches/
    sourcing.py        # branch 1 — what to source
    pricing.py         # branch 2 — reprice for max profit-after-fees
    inventory.py       # branch 3 — restock / reorder-point (per variant)
    adspend.py         # branch 4 — ad-budget allocation by ACOS/ROAS
    returns.py         # branch 6 — stop the return leak (excess returns vs category norm)
  venue/               # venue supply tracking — POS counts -> BOM -> supplies consumed -> reorder
  profile.py           # operator profiles — personalise every branch to who you are
  edges.py             # true edge — fuse 7 edge angles, flag what's CORNERABLE
  arbitrage.py         # buy-low/sell-high: temporal (Keepa) now, cross-channel pluggable
  timing.py            # sales-rank momentum — rising vs fading (live `tim` angle)
  branches/scout.py    # read a market through your profile (landscape + ranked opportunities)
  journal.py           # the record: decisions + outcomes (learning loop)
  cli.py / __main__.py # python -m ebe <branch>
tests/                 # unittest suite (python -m unittest discover -s tests)
```

## Roadmap (toward the full platform)

- [x] Universal Genome + fee models
- [x] Branches: sourcing, pricing, inventory, adspend
- [x] First-class apparel/merch (variants + apparel economics)
- [x] CSV import — run every branch on your own catalog / inventory / campaigns
- [x] Live API adapters — Keepa (sourcing) usable now; Amazon SP-API + Ads auth wired ([SETUP.md](SETUP.md))
- [x] `discover` — Keepa Product Finder hands you ranked candidate products to evaluate
- [x] AI Brain — Claude (`claude-opus-4-8`) estimates demand + confidence, caged by the Heart
- [x] Genome v2 — closed learning loop (journal + LearningEyes), sanity gate, portfolio cap, retry/budget guards
- [x] Profiles + `scout` — personalised market landscape + ranked opportunities per operator
- [x] `edges` — fuse 7 edge angles into a true-edge score; flag defensible, cornerable lanes
- [x] `arbitrage` — live temporal buy-the-dip (Keepa); cross-channel via pluggable PriceSource
- [x] Live `edges` — the true-edge engine on real ASINs: live arbitrage + live rank-momentum timing fused in
- [x] **Venue supply tracking (Phase 1)** — POS counts → bill-of-materials → supplies consumed → auto-reorder
- [ ] Phase 2+ — waste/shrinkage detection (BOM-expected vs counted), supply sales, AI forecasting, multi-venue
- [ ] AI Eyes (trend/product recognition) + AI Ears (supplier-data normalization) on Haiku
- [ ] Merge live Amazon stock/price with your `sku,cost` sheet for full profit-after-fees
- [ ] Async Ads reporting (spend/sales) + Shopify & Etsy adapters
- [ ] `TruthMeter` wired to live sell-through so `Eyes` actually graduate patterns
- [ ] Persistence + dashboards
- [ ] **Storefront** (FastAPI) with the genome wired in for auto-pricing & auto-sourcing

## Run the tests

```bash
python -m unittest discover -s tests
```
