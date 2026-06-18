"""
EBE Commerce — a risk-first seller engine for marketplaces (Amazon-style + your own merch).

One Universal Genome, many branches. Each branch is the SAME loop with different cells:
  • sourcing   — which products to buy in (profit after every fee, test-batch first)
  • pricing    — reprice each SKU to its max profit-after-fees price
  • inventory  — restock before you stock out (per-variant for apparel)
  • adspend    — scale ad winners, cut the bleeders

Grow new branches by implementing the seven organs in genome.py.
"""
from .genome import (
    DataFeed, EdgeModel, Risk, Execution, Eyes, BlindEyes, TruthMeter, Machine,
)
from . import fees

__all__ = [
    "DataFeed", "EdgeModel", "Risk", "Execution", "Eyes", "BlindEyes",
    "TruthMeter", "Machine", "fees",
]
__version__ = "0.1.0"
