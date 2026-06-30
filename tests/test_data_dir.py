import os
import importlib
import unittest


class DataDirTests(unittest.TestCase):
    """EBE_DATA_DIR repoints all SQLite files (for a Render persistent disk)."""

    def _reload(self):
        import ebe.store as store
        import ebe.tenancy as tenancy
        importlib.reload(store)
        importlib.reload(tenancy)
        return store, tenancy

    def tearDown(self):
        os.environ.pop("EBE_DATA_DIR", None)
        os.environ.pop("EBE_DB", None)
        self._reload()                         # restore defaults for other tests

    def test_default_is_cwd_relative(self):
        for k in ("EBE_DATA_DIR", "EBE_DB", "EBE_CONTROL_DB", "EBE_TENANT_DIR"):
            os.environ.pop(k, None)
        store, tenancy = self._reload()
        self.assertEqual(store.DEFAULT_DB, "ebe.db")
        self.assertEqual(tenancy.CONTROL_DB, "ebe_tenants.db")
        self.assertEqual(tenancy.TENANT_DIR, "tenants")

    def test_data_dir_repoints_everything(self):
        for k in ("EBE_DB", "EBE_CONTROL_DB", "EBE_TENANT_DIR"):
            os.environ.pop(k, None)
        os.environ["EBE_DATA_DIR"] = "/data"
        store, tenancy = self._reload()
        self.assertEqual(store.DEFAULT_DB, os.path.join("/data", "ebe.db"))
        self.assertEqual(tenancy.CONTROL_DB, os.path.join("/data", "ebe_tenants.db"))
        self.assertEqual(tenancy.TENANT_DIR, os.path.join("/data", "tenants"))

    def test_explicit_db_overrides_data_dir(self):
        os.environ["EBE_DATA_DIR"] = "/data"
        os.environ["EBE_DB"] = "custom.db"
        store, _ = self._reload()
        self.assertEqual(store.DEFAULT_DB, "custom.db")


if __name__ == "__main__":
    unittest.main()
