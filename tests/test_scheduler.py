import unittest

from ebe import scheduler


class FakeStore:
    def __init__(self, tid):
        self.tid = tid
        self.closed = False
    def close(self):
        self.closed = True


class RunTickTests(unittest.TestCase):
    def test_runs_cycle_per_tenant_and_closes(self):
        tenants = lambda: [{"id": "a", "db_path": "a.db"}, {"id": "b", "db_path": "b.db"}]
        made = []
        def factory(t):
            s = FakeStore(t["id"]); made.append(s); return s
        ran = []
        def cycle(s):
            ran.append(s.tid); return {"note": "ok %s" % s.tid}
        out = scheduler.run_tick(tenants, factory, cycle, log=lambda *a: None)
        self.assertEqual(ran, ["a", "b"])
        self.assertEqual([tid for tid, _ in out], ["a", "b"])
        self.assertTrue(all(s.closed for s in made))      # every store closed

    def test_one_tenant_error_does_not_stop_others(self):
        tenants = lambda: [{"id": "bad"}, {"id": "good"}]
        def factory(t):
            return FakeStore(t["id"])
        def cycle(s):
            if s.tid == "bad":
                raise RuntimeError("boom")
            return {"note": "fine"}
        out = scheduler.run_tick(tenants, factory, cycle, log=lambda *a: None)
        d = dict(out)
        self.assertIn("error", d["bad"])
        self.assertEqual(d["good"]["note"], "fine")

    def test_start_loops_until_stopped(self):
        # drive the loop deterministically: sleep_fn raises after 2 ticks to exit
        ticks = {"n": 0}
        tenants = lambda: [{"id": "a"}]
        factory = lambda t: FakeStore("a")
        def cycle(s):
            ticks["n"] += 1
            return {"note": "t"}

        class Stop(Exception):
            pass

        def sleep_fn(_secs):
            if ticks["n"] >= 2:
                raise Stop()

        import threading
        th = scheduler.start(1, tenants, factory, cycle,
                             sleep_fn=sleep_fn, log=lambda *a: None, initial_delay=0)
        th.join(timeout=2)
        self.assertGreaterEqual(ticks["n"], 2)
        self.assertFalse(th.is_alive())


if __name__ == "__main__":
    unittest.main()
