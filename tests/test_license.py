import time
import unittest

from ebe import license as lic


class LicenseCryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priv = lic.generate_keypair(bits=1024)        # small key = fast test
        cls.pub = {"n": cls.priv["n"], "e": cls.priv["e"]}

    def test_valid_token_verifies(self):
        tok = lic.issue("Cloud9 Lounge", 30, self.priv)
        v = lic.verify(tok, self.pub)
        self.assertTrue(v["valid"])
        self.assertEqual(v["client"], "Cloud9 Lounge")

    def test_expired_token_is_rejected(self):
        tok = lic.issue("Late Co", 30, self.priv)
        future = int(time.time()) + 31 * 86400
        self.assertFalse(lic.verify(tok, self.pub, now=future)["valid"])

    def test_tampered_token_fails_signature(self):
        tok = lic.issue("Cloud9", 30, self.priv)
        body, sig = tok.split(".")
        forged = lic._b64(b'{"client":"Pirate","exp":9999999999,"iat":0,"plan":"pro"}') + "." + sig
        self.assertFalse(lic.verify(forged, self.pub)["valid"])

    def test_cannot_forge_without_private_key(self):
        # a different keypair's token must not verify against our public key
        other = lic.generate_keypair(bits=1024)
        tok = lic.issue("Freeloader", 365, other)
        self.assertFalse(lic.verify(tok, self.pub)["valid"])


class LicenseGateTests(unittest.TestCase):
    def test_open_mode_when_not_configured(self):
        # no public key on disk → development/open mode → require() passes
        if lic.load_public() is None:
            self.assertEqual(lic.require()["state"], "open")
        else:
            self.skipTest("a license_pub.json exists in this checkout")


if __name__ == "__main__":
    unittest.main()
