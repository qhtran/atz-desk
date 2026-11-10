"""Trusted-device cookie after successful TOTP — skip MFA for N days on same browser."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from backend.desk_session import session_secret

COOKIE_NAME = "atz_desk_mfa_trust"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def issue_trust_value(profile: dict[str, Any], *, ttl_sec: int) -> str | None:
    """Signed snapshot of profile used to re-issue desk session after password+trust."""
    secret = session_secret()
    if not secret or ttl_sec <= 0:
        return None
    username = str(profile.get("username") or "").strip()
    if not username:
        return None
    now = int(time.time())
    payload = {
        "u": username,
        "e": str(profile.get("email") or "").strip(),
        "n": str(profile.get("name") or "").strip(),
        "id": str(profile.get("uid") or "").strip(),
        "g": [str(g).strip() for g in (profile.get("groups") or []) if str(g).strip()],
        "su": bool(profile.get("is_superuser")),
        "iat": now,
        "exp": now + max(300, int(ttl_sec)),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _b64url_encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_trust_value(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    secret = session_secret()
    if not secret:
        return None
    body, _, sig = token.partition(".")
    if not body or not sig:
        return None
    expect = _b64url_encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = int(payload.get("exp") or 0)
    if exp < int(time.time()):
        return None
    username = str(payload.get("u") or "").strip()
    if not username:
        return None
    groups = payload.get("g") if isinstance(payload.get("g"), list) else []
    return {
        "username": username,
        "email": str(payload.get("e") or ""),
        "name": str(payload.get("n") or ""),
        "uid": str(payload.get("id") or ""),
        "groups": [str(g).strip() for g in groups if str(g).strip()],
        "is_superuser": bool(payload.get("su")),
        "source": "desk_session",
    }


def trust_matches_username(token: str | None, username: str) -> dict[str, Any] | None:
    profile = verify_trust_value(token)
    if not profile:
        return None
    if profile["username"].lower() != str(username or "").strip().lower():
        return None
    return profile
