import io
import unittest
import urllib.error
from unittest import mock

from ebe.adapters import base
from ebe.adapters.base import request_json, Budget, BudgetExceeded, set_budget


class FakeResp:
    def __init__(self, body=b'{"ok": true}'):
        self._body, self.headers = body, {}
    def read(self): return self._body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(b"boom"))


class RetryTests(unittest.TestCase):
    def tearDown(self):
        set_budget(None)

    def test_retries_transient_then_succeeds(self):
        seq = [http_error(503), http_error(429), FakeResp()]
        def fake_urlopen(req, timeout=None):
            x = seq.pop(0)
            if isinstance(x, Exception):
                raise x
            return x
        with mock.patch.object(base.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(base.time, "sleep", lambda s: None):
            self.assertEqual(request_json("GET", "http://x"), {"ok": True})
        self.assertEqual(seq, [])               # all three consumed

    def test_permanent_error_not_retried(self):
        calls = {"n": 0}
        def fake_urlopen(req, timeout=None):
            calls["n"] += 1
            raise http_error(400)               # client error -> no retry
        with mock.patch.object(base.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(base.time, "sleep", lambda s: None):
            with self.assertRaises(base.AdapterError):
                request_json("GET", "http://x")
        self.assertEqual(calls["n"], 1)

    def test_gives_up_after_retries(self):
        def fake_urlopen(req, timeout=None):
            raise http_error(503)
        with mock.patch.object(base.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(base.time, "sleep", lambda s: None):
            with self.assertRaises(base.AdapterError):
                request_json("GET", "http://x", retries=2)


class BudgetTests(unittest.TestCase):
    def tearDown(self):
        set_budget(None)

    def test_budget_blocks_after_limit(self):
        set_budget(Budget(2))
        with mock.patch.object(base.urllib.request, "urlopen", lambda req, timeout=None: FakeResp()):
            request_json("GET", "http://x")
            request_json("GET", "http://x")
            with self.assertRaises(BudgetExceeded):
                request_json("GET", "http://x")


if __name__ == "__main__":
    unittest.main()
