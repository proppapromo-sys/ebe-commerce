import gzip
import unittest

from ebe.adapters.base import _decode


class DecodeTests(unittest.TestCase):
    def test_plain_utf8(self):
        self.assertEqual(_decode(b'{"ok": true}'), '{"ok": true}')

    def test_gunzips_by_magic_bytes(self):
        # Keepa always gzips; the body starts with 1f 8b and no header is needed.
        raw = gzip.compress(b'{"tokensLeft": 1200}')
        self.assertEqual(_decode(raw), '{"tokensLeft": 1200}')

    def test_gunzips_by_content_encoding_header(self):
        raw = gzip.compress(b'{"x": 1}')
        self.assertEqual(_decode(raw, "gzip"), '{"x": 1}')

    def test_empty_body(self):
        self.assertEqual(_decode(b""), "")


if __name__ == "__main__":
    unittest.main()
