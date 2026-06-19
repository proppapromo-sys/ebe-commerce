#!/usr/bin/env python3
"""
base.py — the shared HTTP helper for every live adapter. Pure stdlib (urllib), so the
whole project still installs with zero dependencies. JSON in, JSON out, clear errors.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class AdapterError(Exception):
    """Any failure talking to an external API (HTTP error, network, bad JSON)."""


def request_json(method, url, headers=None, params=None, json_body=None, form=None, timeout=30):
    """One HTTP call returning parsed JSON. Raises AdapterError with the response body
    on non-2xx so you can see exactly what the API complained about."""
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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:800] if e.fp else ""
        raise AdapterError("HTTP %s from %s — %s" % (e.code, url.split("?")[0], detail))
    except urllib.error.URLError as e:
        raise AdapterError("network error reaching %s — %s" % (url.split("?")[0], e.reason))
    return json.loads(body) if body else {}
