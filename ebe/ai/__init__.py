"""
AI organs — Claude wired into the genome, but CAGED by the five laws.

The vision: AI in place where it adds power (the BRAIN's demand read), never where it
adds risk (the HEART's caps and the TruthMeter stay AI-free). The Brain proposes a
number; the genome's edge gate, Kelly sizing and forward-validation wrap it unchanged.

  • brain.AIEdgeModel — Claude estimates real demand + confidence -> edge

Optional dependency: requires `pip install anthropic` and ANTHROPIC_API_KEY in .env.
"""
from .client import available, MODEL

__all__ = ["available", "MODEL"]
