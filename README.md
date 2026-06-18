# EBE Commerce

A **risk-first seller engine** for marketplaces — built to maximise *profit after every
fee*, not vanity revenue. One **Universal Genome** (a reusable decision skeleton), many
**branches** you snap on. Today it's a seller/operator brain for Amazon-style selling and
your own merch/apparel; the architecture is laid out to grow toward a full storefront +
auto-pilot platform later.

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

| Branch | Question it answers | Edge = |
|---|---|---|
| `sourcing` | What should I buy in? | ROI after all fees vs break-even |
| `pricing` | What price makes the most money? | profit uplift vs today's price |
| `inventory` | What's about to stock out? | how far below the reorder point |
| `adspend` | Where should ad money go? | headroom under target ACOS |

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
  cli.py / __main__.py # python -m ebe <branch>
tests/                 # unittest suite (python -m unittest discover -s tests)
```

## Roadmap (toward the full platform)

- [x] Universal Genome + fee models
- [x] Branches: sourcing, pricing, inventory, adspend
- [x] First-class apparel/merch (variants + apparel economics)
- [ ] Real data adapters (Seller-Central / Shopify / supplier scrapers) replacing sample feeds
- [ ] `TruthMeter` wired to live sell-through so `Eyes` actually graduate patterns
- [ ] Persistence + dashboards
- [ ] **Storefront** (FastAPI) with the genome wired in for auto-pricing & auto-sourcing

## Run the tests

```bash
python -m unittest discover -s tests
```
