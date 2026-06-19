#!/usr/bin/env python3
"""
example_picker.py — a worked example built on the Universal Genome seed.

Copy this NEXT TO universal_genome.py to see a real domain wired end-to-end: an Amazon
product picker that sources only what profits AFTER every fee, sizes a small test batch,
and learns which niches actually pay. Use it as the template for your own domain.

  python example_picker.py
"""
from __future__ import annotations

from universal_genome import (
    DataFeed, EdgeModel, Risk, Execution, LearningEyes, Machine, Journal, category_trust,
)

# Amazon's "vig" — fees that quietly eat margin (tune to your category):
REFERRAL, ADS, RETURNS, = 0.15, 0.15, 0.05


def net(p):
    """Profit per unit AFTER every fee — the only number that matters."""
    fees = p["sell"] * (REFERRAL + ADS + RETURNS) + p["fba"]
    return p["sell"] - p["cost"] - fees


# 👂 EARS — products you could source (your scraper / supplier list plugs in here)
class ProductFeed(DataFeed):
    def candidates(self):
        return [
            {"id": "P1", "name": "LED strip lights", "category": "home",   "sell": 22, "cost": 5,  "fba": 4, "monthly_sales": 800, "competition": 0.4},
            {"id": "P2", "name": "Phone case",       "category": "phones", "sell": 25, "cost": 12, "fba": 5, "monthly_sales": 600, "competition": 0.9},
            {"id": "P3", "name": "Yoga mat",         "category": "fitness","sell": 45, "cost": 14, "fba": 6, "monthly_sales": 300, "competition": 0.5},
        ]


# 🧠 BRAIN — edge = ROI after ALL fees (most products look fine until you subtract the vig)
class ProductEdge(EdgeModel):
    def fair(self, p): return 1.0                          # break-even ROI
    def mine(self, p): return (net(p) / p["cost"]) + 1.0   # your true return-on-cost


# ❤️ HEART — order a SMALL TEST BATCH; never tie up too much in one unproven SKU
class ProductRisk(Risk):
    def __init__(self, capital, test_units=15):
        super().__init__(capital, min_edge=0.30, max_per=0.20)
        self.test_units = test_units

    def kelly(self, p, edge): return edge

    def stake(self, p, edge):
        if p["monthly_sales"] < 100:                      # no demand -> don't even test
            return 0.0
        return round(min(self.test_units * p["cost"], self.max_per * self.bankroll), 2)


# ✋ HANDS — confirm-first "source a test batch"
class ProductExec(Execution):
    def place(self, p, stake, live=False):
        units = int(stake / p["cost"])
        print("    📦 SOURCE %-18s %d units · $%.0f (ROI %.0f%% after fees, $%.2f/unit)"
              % (p["name"], units, stake, (net(p) / p["cost"]) * 100, net(p)))


# 👁️ EYES — recognise the niche; LEARN which niches actually profit
class ProductEyes(LearningEyes):
    def detect(self, p):
        pats = [{"name": "niche:" + p["category"], "dir": 1}]
        if p["competition"] >= 0.8:
            pats.append({"name": "saturated", "dir": -1})
        return pats


if __name__ == "__main__":
    jrnl = Journal()
    m = Machine(ProductFeed(), ProductEdge(), ProductRisk(capital=2000),
                ProductEyes(), ProductExec(), name="picker", journal=jrnl)
    print("PRODUCT PICKER — gate: ≥30% ROI after fees · 15-unit test · ≥100 sales/mo\n")
    tickets = m.cycle(place=True)

    # forward-validate: pretend 'home' sold through, 'fitness' didn't — the record teaches the eyes
    for d in [r for r in jrnl.read() if r["kind"] == "decision"]:
        jrnl.record_outcome("picker", d["id"], 1.0 if d["category"] == "home" else -1.0)
    print("\nlearned niche trust:", {k: round(v, 2) for k, v in category_trust(jrnl.read()).items()})
