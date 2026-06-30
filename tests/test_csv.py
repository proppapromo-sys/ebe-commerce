import os
import tempfile
import unittest

from ebe.catalog.csv_io import load_products, load_campaigns

PRODUCTS = (
    "id,name,category,cost,sell,fulfilment,competition,lead_time_days,elasticity,size,color,on_hand,monthly_sales\n"
    "P1,LED,home,5,22,4,0.4,18,1.8,,,900,800\n"
    "M1,Tee,apparel,9,28,5,0.5,21,1.6,S,Black,15,40\n"
    "M1,Tee,apparel,9,28,5,0.5,21,1.6,M,Black,60,120\n"
)

CAMPAIGNS = (
    "id,name,category,sell,cost,spend,ad_sales,target_acos\n"
    "C-P1,LED,home,22,5,600,4200,0.25\n"
)


def _tmp(text):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


class CsvProductTests(unittest.TestCase):
    def setUp(self):
        self.path = _tmp(PRODUCTS)
    def tearDown(self):
        os.remove(self.path)

    def test_simple_product_parsed(self):
        prods = {p.id: p for p in load_products(self.path)}
        led = prods["P1"]
        self.assertFalse(led.is_apparel)
        self.assertEqual(led.cost, 5)
        self.assertEqual(led.on_hand, 900)
        self.assertEqual(led.monthly_sales, 800)

    def test_variant_rows_group_into_one_apparel_product(self):
        prods = {p.id: p for p in load_products(self.path)}
        tee = prods["M1"]
        self.assertTrue(tee.is_apparel)
        self.assertEqual(len(tee.variants), 2)
        self.assertEqual(tee.total_on_hand, 75)             # 15 + 60
        self.assertEqual(tee.total_monthly_sales, 160)      # 40 + 120
        self.assertEqual({v.sku for v in tee.variants}, {"S/Black", "M/Black"})

    def test_order_preserved(self):
        ids = [p.id for p in load_products(self.path)]
        self.assertEqual(ids, ["P1", "M1"])


class CsvCampaignTests(unittest.TestCase):
    def test_campaign_parsed(self):
        path = _tmp(CAMPAIGNS)
        try:
            c = load_campaigns(path)[0]
            self.assertEqual(c["id"], "C-P1")
            self.assertEqual(c["spend"], 600)
            self.assertEqual(c["target_acos"], 0.25)
        finally:
            os.remove(path)


class CsvExampleFilesTests(unittest.TestCase):
    """The shipped example CSVs must stay loadable."""
    def test_example_products_and_campaigns_load(self):
        root = os.path.join(os.path.dirname(__file__), "..", "examples")
        prods = load_products(os.path.join(root, "products.csv"))
        camps = load_campaigns(os.path.join(root, "campaigns.csv"))
        self.assertTrue(prods and camps)
        self.assertTrue(any(p.is_apparel for p in prods))


if __name__ == "__main__":
    unittest.main()
