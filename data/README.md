# Your EBE data — first real products

This folder holds *your* live business data (edit these, not the `examples/`).
Two products are seeded from the sourcing you already did:

| SKU | What | Landed cost | Sell | Channel |
|---|---|---|---|---|
| `COCO-CHARCOAL-1.2KG` | Coconut charcoal 1.2kg / 84ct | $3.00 | $14.99 | ship (Amazon/Shopify) — **CORNER** |
| `CLAMSHELL-9x9-50` | Compostable clamshell 9×9 (50pk) | $6.50 | $15.00 | **local delivery** — 50% margin |

## Load it (two commands)
```powershell
cd $HOME\ebe-commerce
python -m ebe catalog --db ebe.db --products data\products.csv      # load the catalog
python -m ebe vendors --db ebe.db --file data\vendor_offers.csv     # load the Alibaba bids
```

## Run the engine on it
```powershell
python -m ebe rank   --file data\products.csv --fees local  --profile hookah   # rank by edge+margin
python -m ebe rebuy  --db ebe.db                                                # auto re-buy (vendor auction)
python -m ebe brief  --db ebe.db                                                # the morning rundown
python -m ebe dashboard --db ebe.db                                             # the cockpit
```

## Clamshell pricing (locked from the analysis)
- **Target: $15 / 50-pack ($0.30/box)** — 50% margin, undercuts Amazon's $0.45/box by a third.
- **Floor: ~$11 / pack** — never sell below. In the repricer that's roughly:
  ```powershell
  python -m ebe reprice --db ebe.db --fees local --floor-roi 0.54
  ```
- Ceiling: ~$18/pack (still under Amazon).

## As you source more
Add a row to `products.csv` (and a bid to `vendor_offers.csv`) for each new product,
re-run `catalog` + `vendors`, and the whole engine — auction, re-buy, MRR, ledger,
statements, audit — tracks it automatically.
