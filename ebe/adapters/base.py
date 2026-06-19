#!/usr/bin/env python3
"""
base.py — the shared HTTP helper for every live adapter. Pure stdlib (urllib), so the
whole project still installs with zero dependencies. JSON in, JSON out, clear errors.

Operational guards (genome v2):
  • retry with exponential backoff on transient failures (429 / 5xx / network),
    honouring a Retry-After header when the server sends one;
  • an optional call Budget so a runaway loop can't burn unlimited Keepa tokens
    or Anthropic spend — set_budget(Budget(max_calls)) and every call is counted.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request

TRANSIENT = {429, 500, 502, 503, 504, 529}     # worth retrying; 4xx (except 429) is not


class AdapterError(Exception):
    """Any failure talking to an external API (HTTP error, network, bad JSON)."""


class BudgetExceeded(AdapterError):
    """The configured external-call budget was exhausted — stop before spending more."""


class Budget:
    """A simple ceiling on outbound API calls per process (token / cost safety)."""
    def __init__(self, max_calls):
        self.max_calls = int(max_calls)
        self.calls = 0

    def spend(self, n=1):
        self.calls += n
        if self.calls > self.max_calls:
            raise BudgetExceeded("API call budget exhausted (limit %d)" % self.max_calls)


_BUDGET = None


def set_budget(budget):
    """Install a process-wide call Budget (or None to clear)."""
    global _BUDGET
    _BUDGET = budget


def _decode(raw, content_encoding=None):
    """Decode a response body to text, transparently gunzipping when needed.
    Some APIs (e.g. Keepa) always gzip their responses; urllib doesn't unzip for us."""
    if raw[:2] == b"\x1f\x8b" or content_encoding == "gzip":   # gzip magic bytes
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def _retry_after(err, attempt, backoff):
    """Seconds to wait before the next attempt — server's Retry-After if given, else backoff."""
    try:
        ra = err.headers.get("Retry-After") if getattr(err, "headers", None) else None
        if ra is not None:
            return float(ra)
    except (ValueError, AttributeError):
        pass
    return backoff * (2 ** attempt)


def request_json(method, url, headers=None, params=None, json_body=None, form=None,
                 timeout=30, retries=3, backoff=1.0):
    """One HTTP call returning parsed JSON. Retries transient failures with backoff.
    Raises AdapterError with the response body on a permanent non-2xx."""
    if _BUDGET is not None:
        _BUDGET.spend()                         # counts as one logical call (retries are free)

    headers = dict(headers or {})
    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers.setdefault("Content-Type", "application/json")
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = _decode(resp.read(), resp.headers.get("Content-Encoding"))
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code in TRANSIENT and attempt < retries:
                time.sleep(_retry_after(e, attempt, backoff))
                attempt += 1
                continue
            detail = _decode(e.read(), e.headers.get("Content-Encoding"))[:800] if e.fp else ""
            raise AdapterError("HTTP %s from %s — %s" % (e.code, url.split("?")[0], detail))
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                attempt += 1
                continue
            raise AdapterError("network error reaching %s — %s" % (url.split("?")[0], e.reason))
