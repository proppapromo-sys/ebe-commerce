import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import unittest

from ebe import billing
from ebe.tenancy import Tenants


def _sig(payload: bytes, secret: str, t=None):
    t = int(time.time()) if t is None else t
    v1 = hmac.new(secret.encode(), ("%d." % t).encode() + payload, hashlib.sha256).hexdigest()
    return "t=%d,v1=%s" % (t, v1)


class SignatureTests(unittest.TestCase):
    def test_valid_signature_passes(self):
        p = b'{"hello":"world"}'
        self.assertTrue(billing.verify_signature(p, _sig(p, "whsec_x"), "whsec_x"))

    def test_wrong_secret_fails(self):
        p = b'{"hello":"world"}'
        self.assertFalse(billing.verify_signature(p, _sig(p, "whsec_x"), "whsec_y"))

    def test_stale_timestamp_rejected(self):
        p = b'{}'
        old = _sig(p, "s", t=int(time.time()) - 9999)
        self.assertFalse(billing.verify_signature(p, old, "s"))


class EventHandlingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.tn = Tenants(path=os.path.join(self.dir, "c.db"),
                          tenant_dir=os.path.join(self.dir, "t"))
        self.tn.create_tenant("cloud9", "Cloud9", "p", days=0)
        self.tn.suspend("cloud9")                          # starts locked, awaiting payment

    def tearDown(self):
        self.tn.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_checkout_completed_links_and_activates(self):
        ev = {"type": "checkout.session.completed",
              "data": {"object": {"client_reference_id": "cloud9", "customer": "cus_123"}}}
        billing.handle_event(self.tn, ev)
        self.assertTrue(self.tn.is_entitled("cloud9"))
        self.assertEqual(self.tn.tenant("cloud9")["stripe_customer"], "cus_123")

    def test_recurring_invoice_paid_renews_by_customer(self):
        self.tn.link_stripe("cloud9", "cus_123")
        billing.handle_event(self.tn, {"type": "invoice.paid",
                                       "data": {"object": {"customer": "cus_123"}}})
        self.assertTrue(self.tn.is_entitled("cloud9"))

    def test_payment_failed_suspends(self):
        self.tn.link_stripe("cloud9", "cus_123")
        self.tn.renew("cloud9", 31)
        self.assertTrue(self.tn.is_entitled("cloud9"))
        billing.handle_event(self.tn, {"type": "invoice.payment_failed",
                                       "data": {"object": {"customer": "cus_123"}}})
        self.assertFalse(self.tn.is_entitled("cloud9"))

    def test_unknown_event_is_ignored(self):
        self.assertIn("ignored", billing.handle_event(self.tn, {"type": "ping", "data": {"object": {}}}))


if __name__ == "__main__":
    unittest.main()
