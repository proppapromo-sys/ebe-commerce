import unittest

from ebe.venue.bom import explode_usage
from ebe.venue.engine import to_restock_items, run
from ebe.venue.sample import sample_menu, sample_consumables, sample_sales


class BomTests(unittest.TestCase):
    def test_explode_usage(self):
        usage = explode_usage(sample_sales(), sample_menu())
        # 120 hookahs × 4 coco = 480 charcoal; 500 drinks × 1 cup = 500; 85 takeout containers
        self.assertEqual(usage["charcoal_coco"], 480)
        self.assertEqual(usage["cup_clear"], 500)
        self.assertEqual(usage["container_3c"], 85)
        self.assertEqual(usage["napkin"], 1000)        # 500 drinks × 2

    def test_unknown_menu_item_ignored(self):
        self.assertEqual(explode_usage({"ghost": 99}, sample_menu()), {})


class EngineTests(unittest.TestCase):
    def test_to_restock_items_carries_usage_as_demand(self):
        usage = explode_usage(sample_sales(), sample_menu())
        items = {i["id"]: i for i in to_restock_items(usage, sample_consumables())}
        self.assertEqual(items["charcoal_coco"]["monthly_sales"], 480)
        self.assertEqual(items["charcoal_coco"]["pack_size"], 1000)

    def test_period_scales_to_monthly(self):
        # 240 charcoal over 15 days -> 480/month
        usage = {"charcoal_coco": 240}
        items = {i["id"]: i for i in to_restock_items(usage, sample_consumables(), period_days=15)}
        self.assertAlmostEqual(items["charcoal_coco"]["monthly_sales"], 480.0)

    def test_run_reorders_the_hot_supplies_only(self):
        tickets = run(sample_sales(), sample_menu(), sample_consumables(), place=False)
        ids = {t[0]["id"] for t in tickets}
        self.assertIn("charcoal_coco", ids)       # 480/mo vs 300 on hand -> below reorder point
        self.assertIn("container_3c", ids)        # 85/mo vs 40 on hand
        self.assertIn("hose_tip", ids)            # 120/mo vs 80 on hand
        self.assertNotIn("cup_clear", ids)        # 500/mo vs 600 on hand, short lead -> fine
        self.assertNotIn("napkin", ids)           # huge buffer


if __name__ == "__main__":
    unittest.main()
