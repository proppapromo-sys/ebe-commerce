# Universal Genome v2 — project seed

Copy **`universal_genome.py`** into a new project and you have a complete, risk-first,
self-learning decision engine. Pure standard library — no installs, runs anywhere.

```bash
cp seed/universal_genome.py ~/my-new-project/genome.py
cd ~/my-new-project && python genome.py        # runs the end-to-end demo
```

## The five laws (the DNA)
1. **Risk-first**, not prediction-first — survive before you win.
2. **Edge = your number vs the world's** — no edge, no action.
3. **Forward-validate** before real stakes — the journal is the truth-meter.
4. **Recognise + remember**, don't predict — trust is earned on your record.
5. **Confirm-first, never chase** — no revenge, no size-up on a streak.

## Start a new domain in ~40 lines
Implement five organs, hand them to `Machine`:

```python
from genome import DataFeed, EdgeModel, Risk, Execution, LearningEyes, Machine, Journal, category_trust

class Feed(EdgeModel): ...        # 👂 candidates() -> [ {id, category, ...}, ... ]
class Edge(EdgeModel):            # 🧠 your number vs the world's
    def fair(self, it): ...       #    the world's estimate
    def mine(self, it): ...       #    your estimate  (edge = mine - fair)
class MyRisk(Risk):               # ❤️ build this first
    def kelly(self, it, edge): return ...   # fraction of bankroll (¼-Kelly, capped, applied for you)
class Hands(Execution):           # ✋ confirm-first; dry-run unless live=True
    def place(self, it, stake, live=False): ...
class Sight(LearningEyes):        # 👁️ patterns that graduate on the record
    def detect(self, it): return [{"name": "cat:" + it["category"], "dir": 1}]

journal = Journal("record.jsonl")           # or Journal() for in-memory
m = Machine(Feed(), Edge(), MyRisk(bankroll=1000), Sight(), Hands(), journal=journal)
m.cycle(place=True)                          # gate -> size -> act -> record
```

## Make it compound (laws 3 & 4)
```python
# after you observe real results, score each decision:
journal.record_outcome("machine", item_id, score=+1.0)   # >0 = it worked

learned = category_trust(journal.read())     # proven categories climb, duds sink
sight = Sight(trust_table=pattern_trust(journal.read()))  # graduated patterns start voting
```
Re-run with the learned table and the engine is sharper than last cycle — an edge that
**grows from your own record** and that competitors don't have.

## What's included
`DataFeed · EdgeModel · Risk (+Portfolio) · Execution · Eyes (+BlindEyes, LearningEyes) ·
TruthMeter · Machine` plus `sane_item` (input guard), `Journal` (record),
`pattern_trust` / `category_trust` (learning). One file, ~300 lines, fully self-contained.

This is the same skeleton behind EBE Command's sourcing, pricing, inventory, ad-spend,
returns, scout, and venue branches — proof it generalises.
