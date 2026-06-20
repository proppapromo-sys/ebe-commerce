import os
import shutil
import tempfile
import time
import unittest

from ebe.tenancy import Tenants


class TenancyTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.tn = Tenants(path=os.path.join(self.dir, "ctrl.db"),
                          tenant_dir=os.path.join(self.dir, "tenants"))

    def tearDown(self):
        self.tn.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_create_and_authenticate(self):
        self.tn.create_tenant("cloud9", "Cloud9 Lounge", "s3cret", days=30)
        self.assertTrue(self.tn.authenticate("cloud9", "s3cret"))
        self.assertFalse(self.tn.authenticate("cloud9", "wrong"))
        self.assertFalse(self.tn.authenticate("ghost", "x"))

    def test_each_tenant_gets_isolated_db_path(self):
        a = self.tn.create_tenant("a", "A", "p")
        b = self.tn.create_tenant("b", "B", "p")
        self.assertNotEqual(a["db_path"], b["db_path"])

    def test_entitlement_true_when_active_and_unexpired(self):
        self.tn.create_tenant("c9", "C9", "p", days=30)
        self.assertTrue(self.tn.is_entitled("c9"))

    def test_expired_subscription_locks_out(self):
        self.tn.create_tenant("late", "Late", "p", days=30)
        future = time.time() + 31 * 86400
        self.assertFalse(self.tn.is_entitled("late", now=future))

    def test_suspend_blocks_then_resume_and_renew_restore(self):
        self.tn.create_tenant("c9", "C9", "p", days=30)
        self.tn.suspend("c9")
        self.assertFalse(self.tn.is_entitled("c9"))
        self.tn.resume("c9")
        self.assertTrue(self.tn.is_entitled("c9"))

    def test_renew_extends_expiry_and_reactivates(self):
        self.tn.create_tenant("c9", "C9", "p", days=1)
        self.tn.suspend("c9")
        self.tn.renew("c9", days=30)
        self.assertTrue(self.tn.is_entitled("c9"))
        self.assertGreater(self.tn.tenant("c9")["expires"], time.time() + 20 * 86400)

    def test_password_is_hashed_not_stored_plain(self):
        t = self.tn.create_tenant("c9", "C9", "supersecret")
        self.assertNotIn("supersecret", t["pw_hash"])
        self.assertTrue(len(t["pw_hash"]) >= 32)


if __name__ == "__main__":
    unittest.main()
