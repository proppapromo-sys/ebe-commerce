import unittest

from ebe.ai.brain import AIEdgeModel, build
from ebe.catalog.feeds import ListFeed
from ebe.catalog.product import Product
from ebe.fees import AMAZON_FBA


def stub_assess(verdicts):
    """Return an assess_fn that reads canned verdicts by product id (no network)."""
    def _assess(p):
        return verdicts[p["id"]]
    return _assess


class AIBrainTests(unittest.TestCase):
    def test_confidence_scales_the_edge(self):
        p = {"id": "X", "name": "thing", "category": "home", "cost": 5, "sell": 22,
             "competition": 0.4, "monthly_sales": 0}
        roi = AMAZON_FBA.roi(22, 5)
        sure = AIEdgeModel(AMAZON_FBA, stub_assess(
            {"X": {"expected_monthly_sales": 800, "saturation": 0.3, "confidence": 1.0, "rationale": "."}}))
        unsure = AIEdgeModel(AMAZON_FBA, stub_assess(
            {"X": {"expected_monthly_sales": 800, "saturation": 0.3, "confidence": 0.1, "rationale": "."}}))
        self.assertAlmostEqual(sure.edge(dict(p)), roi * 1.0)
        self.assertAlmostEqual(unsure.edge(dict(p)), roi * 0.1)
        self.assertLess(unsure.edge(dict(p)), sure.edge(dict(p)))

    def test_ai_demand_feeds_the_item(self):
        p = {"id": "Y", "name": "thing", "category": "home", "cost": 5, "sell": 22,
             "competition": 0.4, "monthly_sales": 0}
        m = AIEdgeModel(AMAZON_FBA, stub_assess(
            {"Y": {"expected_monthly_sales": 650, "saturation": 0.2, "confidence": 0.9, "rationale": "."}}))
        m.edge(p)
        self.assertEqual(p["monthly_sales"], 650)   # AI's read now drives Risk sizing
        self.assertEqual(p["_ai"]["confidence"], 0.9)

    def test_unsure_ai_does_not_clear_the_gate(self):
        # A profitable product the AI is NOT confident about should be passed over.
        prods = [Product("Z", "Maybe widget", "home", cost=5, sell=22, competition=0.4)]
        verdicts = {"Z": {"expected_monthly_sales": 800, "saturation": 0.3,
                          "confidence": 0.05, "rationale": "too speculative"}}
        m = build(ListFeed(prods), fee_model=AMAZON_FBA, assess_fn=stub_assess(verdicts))
        self.assertEqual(m.cycle(), [])             # edge = roi×0.05 < 30% gate

    def test_confident_profitable_ai_clears(self):
        prods = [Product("G", "Good widget", "home", cost=5, sell=22, competition=0.4)]
        verdicts = {"G": {"expected_monthly_sales": 800, "saturation": 0.3,
                          "confidence": 0.95, "rationale": "strong, open lane"}}
        m = build(ListFeed(prods), fee_model=AMAZON_FBA, assess_fn=stub_assess(verdicts))
        ids = [t[0]["id"] for t in m.cycle()]
        self.assertIn("G", ids)


class PingTests(unittest.TestCase):
    def test_ping_without_key_raises_cleanly(self):
        import os
        from ebe.adapters import config
        from ebe.adapters.base import AdapterError
        from ebe.ai.client import ping
        os.environ.pop("ANTHROPIC_API_KEY", None)
        config._LOADED = True            # don't read a .env file during the test
        with self.assertRaises(AdapterError):
            ping()


if __name__ == "__main__":
    unittest.main()
