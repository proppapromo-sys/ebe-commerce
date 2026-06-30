import contextlib
import io
import os
import tempfile
import unittest

from ebe.cli import main
from ebe.journal import Journal


class CommandTests(unittest.TestCase):
    def test_command_renders_one_consolidated_report(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["command"])
        out = buf.getvalue()
        self.assertIn("EBE COMMAND · TODAY", out)
        self.assertIn("STOP THE LEAK", out)        # returns section
        self.assertIn("REORDER", out)              # inventory section
        self.assertIn("action(s) today", out)      # summary line


class OutcomeTests(unittest.TestCase):
    def test_win_records_positive_outcome(self):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main(["outcome", "--journal", path, "--id", "P1", "--win"])
            recs = Journal(path).read()
            self.assertEqual(recs[0]["kind"], "outcome")
            self.assertEqual(recs[0]["id"], "P1")
            self.assertEqual(recs[0]["score"], 1.0)
        finally:
            os.remove(path)

    def test_score_flag(self):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["outcome", "--journal", path, "--id", "X", "--score", "-2"])
            self.assertEqual(Journal(path).read()[0]["score"], -2.0)
        finally:
            os.remove(path)

    def test_requires_id_and_result(self):
        with self.assertRaises(SystemExit):
            main(["outcome", "--journal", "x.jsonl"])          # no --id


if __name__ == "__main__":
    unittest.main()
