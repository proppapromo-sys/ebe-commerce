import os
import io
import tempfile
import unittest
from contextlib import redirect_stdout

from ebe import cli
from ebe.store import Store


class ScoreCliTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = Store(self.path)
        s.upsert_products([
            {"sku": "WIN", "name": "High Margin", "cost": 2, "sell": 30, "monthly_sales": 400},
            {"sku": "DOG", "name": "Thin Margin", "cost": 9, "sell": 10, "monthly_sales": 5},
        ])
        s.close()

    def tearDown(self):
        os.remove(self.path)

    def _run(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["score", "--db", self.path, *argv])
        return buf.getvalue()

    def test_score_runs_and_ranks(self):
        out = self._run()
        self.assertIn("CATALOG SCORE", out)
        self.assertIn("High Margin", out)
        self.assertIn("Thin Margin", out)
        # the high-margin SKU should appear before the thin one (ranked by profit)
        self.assertLess(out.index("High Margin"), out.index("Thin Margin"))

    def test_score_empty_catalog_errors(self):
        fd, empty = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with self.assertRaises(SystemExit):
                cli.main(["score", "--db", empty])
        finally:
            os.remove(empty)


if __name__ == "__main__":
    unittest.main()
