import os
import tempfile
import unittest

from ebe import tenancy
from ebe.tenancy import Tenants, SeatLimitError


class InviteAndLoginTests(unittest.TestCase):
    def setUp(self):
        fd, self.ctrl = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.dir = tempfile.mkdtemp()
        self.tn = Tenants(path=self.ctrl, tenant_dir=self.dir)
        self.tn.create_tenant("acme", "Acme Co", "ownerpw", days=30, plan="growth")

    def tearDown(self):
        self.tn.close()
        os.remove(self.ctrl)

    def test_invite_returns_token_and_user_is_invited(self):
        token = self.tn.add_user("acme", "a@x.com", "member")
        self.assertTrue(token and len(token) >= 16)
        u = self.tn.get_user("acme", "a@x.com")
        self.assertEqual(u["status"], "invited")
        self.assertIsNone(self.tn.authenticate_user("acme", "a@x.com", "anything"))

    def test_accept_invite_sets_password_and_activates(self):
        token = self.tn.add_user("acme", "a@x.com", "admin")
        u = self.tn.accept_invite("acme", token, "secret1")
        self.assertIsNotNone(u)
        self.assertEqual(u["status"], "active")
        # token is single-use
        self.assertIsNone(self.tn.accept_invite("acme", token, "again99"))
        # and now they can log in
        got = self.tn.authenticate_user("acme", "a@x.com", "secret1")
        self.assertIsNotNone(got)
        self.assertEqual(got["role"], "admin")
        self.assertIsNone(self.tn.authenticate_user("acme", "a@x.com", "wrong"))

    def test_bad_token_is_rejected(self):
        self.tn.add_user("acme", "a@x.com")
        self.assertIsNone(self.tn.accept_invite("acme", "deadbeef", "secret1"))

    def test_reinvite_does_not_consume_a_new_seat(self):
        self.tn.create_tenant("solo", "Solo", "pw", plan="starter")  # 1 seat = owner only
        # starter owner fills the only seat, so a first invite must fail
        with self.assertRaises(tenancy.SeatLimitError):
            self.tn.add_user("solo", "a@x.com")
        # growth has room; invite then re-invite the same email keeps one seat
        self.tn.add_user("acme", "a@x.com", "member")
        self.assertEqual(self.tn.seats_used("acme"), 2)
        t2 = self.tn.add_user("acme", "a@x.com", "admin")  # re-invite → new token, same seat
        self.assertEqual(self.tn.seats_used("acme"), 2)
        self.assertEqual(self.tn.get_user("acme", "a@x.com")["role"], "admin")
        self.assertTrue(t2)

    def test_user_role_helper(self):
        self.tn.add_user("acme", "a@x.com", "viewer")
        self.assertEqual(self.tn.user_role("acme", "a@x.com"), "viewer")
        self.assertIsNone(self.tn.user_role("acme", "nobody@x.com"))


class HostPermissionTests(unittest.TestCase):
    def test_write_guard_by_role(self):
        from ebe import host
        # viewer: no writes at all
        self.assertFalse(host._may_write("viewer", "/po"))
        self.assertFalse(host._may_write("viewer", "/catalog-add"))
        self.assertTrue(host._may_write("viewer", "/catalog"))      # reading is fine
        # member: can run the business but not manage the team
        self.assertTrue(host._may_write("member", "/po"))
        self.assertFalse(host._may_write("member", "/settings-invite"))
        # admin / owner: full
        self.assertTrue(host._may_write("admin", "/settings-invite"))
        self.assertTrue(host._may_write("owner", "/settings-remove"))

    def test_invite_link_uses_base_url(self):
        from ebe import host
        old = host.BASE_URL
        try:
            host.BASE_URL = "https://os.ebehq.com"
            link = host._invite_link("acme", "tok123")
            self.assertTrue(link.startswith("https://os.ebehq.com/accept?"))
            self.assertIn("tid=acme", link)
            self.assertIn("token=tok123", link)
        finally:
            host.BASE_URL = old


if __name__ == "__main__":
    unittest.main()
