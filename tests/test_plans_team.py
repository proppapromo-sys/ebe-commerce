import os
import tempfile
import unittest

from ebe import plans
from ebe import tenancy
from ebe.tenancy import Tenants, SeatLimitError


class PlansTests(unittest.TestCase):
    def test_seat_caps(self):
        self.assertEqual(plans.seat_cap("starter"), 1)
        self.assertEqual(plans.seat_cap("growth"), 3)
        self.assertEqual(plans.seat_cap("pro"), 7)
        self.assertEqual(plans.seat_cap("agency"), 20)
        self.assertEqual(plans.seat_cap("bogus"), 1)        # default starter

    def test_includes_and_upgrade_for(self):
        self.assertTrue(plans.includes("starter", "catalog"))
        self.assertFalse(plans.includes("starter", "autopilot"))
        self.assertTrue(plans.includes("growth", "autopilot"))
        self.assertTrue(plans.includes("agency", "white_label"))
        self.assertFalse(plans.includes("pro", "white_label"))
        self.assertEqual(plans.upgrade_for("autopilot"), "growth")
        self.assertEqual(plans.upgrade_for("white_label"), "agency")

    def test_next_seat_upgrade(self):
        self.assertEqual(plans.next_seat_upgrade("starter"), "growth")
        self.assertEqual(plans.next_seat_upgrade("pro"), "agency")
        self.assertIsNone(plans.next_seat_upgrade("agency"))


class TeamUserTests(unittest.TestCase):
    def setUp(self):
        fd, self.ctrl = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.dir = tempfile.mkdtemp()
        self.tn = Tenants(path=self.ctrl, tenant_dir=self.dir)
        self.tn.create_tenant("acme", "Acme Co", "pw", days=30, plan="growth")  # 3 seats

    def tearDown(self):
        self.tn.close()
        os.remove(self.ctrl)

    def test_owner_counts_as_a_seat(self):
        self.assertEqual(self.tn.seats_used("acme"), 1)      # owner
        self.assertEqual(self.tn.seat_cap("acme"), 3)
        self.assertTrue(self.tn.can_add_user("acme"))

    def test_add_users_until_cap_then_block(self):
        self.tn.add_user("acme", "a@x.com", "member")
        self.tn.add_user("acme", "b@x.com", "admin")
        self.assertEqual(self.tn.seats_used("acme"), 3)      # owner + 2
        self.assertFalse(self.tn.can_add_user("acme"))
        # resolve via the module (other tests may reload tenancy, rebinding the class)
        with self.assertRaises(tenancy.SeatLimitError):
            self.tn.add_user("acme", "c@x.com")

    def test_remove_frees_a_seat(self):
        self.tn.add_user("acme", "a@x.com")
        self.tn.add_user("acme", "b@x.com")
        uid = self.tn.list_users("acme")[0]["id"]
        self.tn.remove_user("acme", uid)
        self.assertEqual(self.tn.seats_used("acme"), 2)
        self.assertTrue(self.tn.can_add_user("acme"))

    def test_role_is_validated(self):
        self.tn.add_user("acme", "a@x.com", "bogus")
        self.assertEqual(self.tn.list_users("acme")[0]["role"], "member")   # invalid → member
        uid = self.tn.list_users("acme")[0]["id"]
        self.tn.set_role("acme", uid, "admin")
        self.assertEqual(self.tn.list_users("acme")[0]["role"], "admin")

    def test_starter_has_one_seat(self):
        self.tn.create_tenant("solo", "Solo", "pw", plan="starter")
        self.assertFalse(self.tn.can_add_user("solo"))       # owner already fills the 1 seat


if __name__ == "__main__":
    unittest.main()
