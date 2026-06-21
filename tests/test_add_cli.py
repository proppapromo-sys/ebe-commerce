import os
import tempfile
import unittest

from ebe import cli
from ebe.store import Store


class AddCliTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        # license is "open" (developer mode) when no public key is shipped — no gate

    def tearDown(self):
        os.remove(self.path)

    def _run(self, *argv):
        cli.main(["add", "--db", self.path, *argv])

    def test_add_creates_product(self):
        self._run("--sku", "WIDGET-1", "--name", "Widget", "--cost", "2.5",
                  "--sell", "9.99", "--on-hand", "40", "--monthly", "120")
        s = Store(self.path)
        p = s.product("WIDGET-1")
        s.close()
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], "Widget")
        self.assertEqual(p["cost"], 2.5)
        self.assertEqual(p["sell"], 9.99)
        self.assertEqual(p["on_hand"], 40)
        self.assertEqual(p["monthly_sales"], 120)

    def test_add_is_partial_update(self):
        self._run("--sku", "WIDGET-1", "--name", "Widget", "--cost", "2.5", "--sell", "9.99")
        self._run("--sku", "WIDGET-1", "--sell", "12.50")     # change only the price
        s = Store(self.path)
        p = s.product("WIDGET-1")
        s.close()
        self.assertEqual(p["sell"], 12.50)
        self.assertEqual(p["name"], "Widget")                 # untouched
        self.assertEqual(p["cost"], 2.5)                      # untouched

    def test_add_requires_sku(self):
        with self.assertRaises(SystemExit):
            self._run("--name", "No SKU")


if __name__ == "__main__":
    unittest.main()
