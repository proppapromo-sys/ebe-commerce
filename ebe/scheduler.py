#!/usr/bin/env python3
"""
scheduler.py — IN-PROCESS AUTOPILOT for the hosted server. Render (and most PaaS) attach
a persistent disk to ONE service, so a separate cron job can't see the web service's
database. The fix: run autopilot on a background thread INSIDE the web process, sharing
the same data. Each tick runs one autopilot cycle for every entitled tenant.

Enabled by EBE_AUTOPILOT_MINUTES (0/unset = off). Logs go to the service's normal logs.

  from ebe import scheduler
  scheduler.start(60, tenants, store_factory, cycle_fn)   # every hour, daemon thread
"""
from __future__ import annotations

import threading
import time


def run_tick(tenants, store_factory, cycle_fn, log=print) -> list:
    """Run ONE autopilot cycle per tenant. Never raises — per-tenant errors are captured."""
    results = []
    for t in tenants():
        tid = t.get("id")
        try:
            store = store_factory(t)
            try:
                res = cycle_fn(store)
            finally:
                try:
                    store.close()
                except Exception:
                    pass
            results.append((tid, res))
            log("[autopilot] %s · %s" % (tid, res.get("note", res) if isinstance(res, dict) else res))
        except Exception as e:
            results.append((tid, {"error": str(e)}))
            log("[autopilot] %s ERROR · %s" % (tid, e))
    return results


def start(every_minutes, tenants, store_factory, cycle_fn,
          sleep_fn=time.sleep, log=print, initial_delay=20):
    """Spawn a daemon thread that runs run_tick every `every_minutes`. Returns the thread."""
    def loop():
        sleep_fn(initial_delay)                 # let the web server settle first
        while True:
            try:
                run_tick(tenants, store_factory, cycle_fn, log)
            except Exception as e:              # a bad tick must never kill the loop
                log("[autopilot] tick failed · %s" % e)
            sleep_fn(max(1, int(every_minutes)) * 60)

    th = threading.Thread(target=loop, name="ebe-autopilot", daemon=True)
    th.start()
    return th
