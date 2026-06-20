#!/usr/bin/env python3
"""
license.py — THE PAYWALL. EBE runs only for a client with a valid, unexpired license.
You (the owner) hold the private key, so you always run free and you alone can mint
licenses; a client who stops paying simply doesn't get a fresh token and the system locks.

Pure-Python RSA (stdlib only): clients VERIFY with the public key shipped in the app, but
cannot FORGE without your private key. Tie "subscription" to the license expiry — issue a
30-day token when they pay, re-issue each month; miss a payment, it lapses, EBE locks.

  python -m ebe license --keygen                       # owner, once: make your key
  python -m ebe license --issue "Cloud9 Lounge" --days 30   # owner: a client's token
  python -m ebe license --check                        # anyone: am I licensed?

NOTE: client-side checks deter casual non-payment but a determined client with the source
can patch them out. For hard enforcement, host the dashboard/storefront yourself and give
clients web logins you can switch off — see the note at the bottom of this file.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time

OWNER_KEY = os.environ.get("EBE_OWNER_KEY", "owner_private.key")   # gitignored — owner only
PUBLIC_KEY = os.path.join(os.path.dirname(__file__), "license_pub.json")  # shipped to clients
LICENSE_FILE = os.environ.get("EBE_LICENSE_FILE", "license.key")
PUBLIC_EXPONENT = 65537


class LicenseError(Exception):
    """Raised when EBE is run without a valid license."""


# ── tiny RSA (stdlib big-int math; fine for license tokens) ──────────────────
def _is_prime(n, rounds=24):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2; r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _gen_prime(bits):
    while True:
        cand = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_prime(cand):
            return cand


def generate_keypair(bits=2048):
    """Owner runs once. Returns {n, e, d}; keep d (private) secret, ship n/e (public)."""
    half = bits // 2
    while True:
        p, q = _gen_prime(half), _gen_prime(half)
        if p == q:
            continue
        n = p * q
        phi = (p - 1) * (q - 1)
        e = PUBLIC_EXPONENT
        try:
            d = pow(e, -1, phi)            # modular inverse (Python 3.8+)
        except ValueError:
            continue
        return {"n": n, "e": e, "d": d}


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _ub64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _digest_int(payload_bytes, n):
    return int.from_bytes(hashlib.sha256(payload_bytes).digest(), "big") % n


def issue(client, days, priv, plan="pro"):
    """Owner mints a license token valid for `days`."""
    now = int(time.time())
    payload = {"client": client, "plan": plan, "iat": now, "exp": now + int(days) * 86400}
    pb = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = pow(_digest_int(pb, priv["n"]), priv["d"], priv["n"])
    siglen = (priv["n"].bit_length() + 7) // 8
    return _b64(pb) + "." + _b64(sig.to_bytes(siglen, "big"))


def verify(token, pub, now=None):
    """Check a token against the public key. Returns a status dict (valid True/False)."""
    now = int(time.time()) if now is None else now
    try:
        pb_s, sig_s = token.strip().split(".")
        pb = _ub64(pb_s)
        sig = int.from_bytes(_ub64(sig_s), "big")
        if pow(sig, pub["e"], pub["n"]) != _digest_int(pb, pub["n"]):
            return {"valid": False, "reason": "bad signature"}
        payload = json.loads(pb)
    except Exception:
        return {"valid": False, "reason": "malformed license"}
    if payload.get("exp", 0) < now:
        return {"valid": False, "reason": "expired", **payload}
    return {"valid": True, "reason": "ok", **payload}


# ── files ────────────────────────────────────────────────────────────────────
def save_keypair(priv, owner_path=OWNER_KEY, pub_path=PUBLIC_KEY):
    with open(owner_path, "w", encoding="utf-8") as fh:
        json.dump(priv, fh)
    with open(pub_path, "w", encoding="utf-8") as fh:
        json.dump({"n": priv["n"], "e": priv["e"]}, fh)


def load_public(path=PUBLIC_KEY):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_private(path=OWNER_KEY):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def current_token():
    return os.environ.get("EBE_LICENSE") or (
        open(LICENSE_FILE, encoding="utf-8").read() if os.path.exists(LICENSE_FILE) else None)


def status():
    """Where this install stands: owner / licensed / unlicensed / open (not armed)."""
    pub = load_public()
    if pub is None:
        return {"state": "open", "msg": "licensing not configured (developer mode)"}
    if load_private() is not None:
        return {"state": "owner", "msg": "owner key present — full access"}
    tok = current_token()
    if not tok:
        return {"state": "unlicensed", "msg": "no license — subscription required"}
    v = verify(tok, pub)
    if v["valid"]:
        import datetime
        exp = datetime.date.fromtimestamp(v["exp"]).isoformat()
        return {"state": "licensed", "msg": "licensed to %s · plan %s · expires %s"
                % (v.get("client"), v.get("plan"), exp), **v}
    return {"state": "unlicensed", "msg": "license %s" % v["reason"], **v}


def require(owner_email="proppapromo@gmail.com"):
    """Gate: raise LicenseError unless this install is the owner or validly licensed.
    Open (un-armed) installs pass, so development and tests aren't blocked."""
    st = status()
    if st["state"] in ("open", "owner", "licensed"):
        return st
    raise LicenseError(
        "⛔ EBE COMMAND — subscription required.\n"
        "   %s\n"
        "   Contact %s to activate or renew your license, then set it:\n"
        "     setx EBE_LICENSE \"<your-license-token>\"   (or save it to license.key)"
        % (st["msg"], owner_email))
