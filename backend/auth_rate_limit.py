"""In-process + optional Redis rate limit for Desk Session auth endpoints.

Used on ``/api/auth/login`` (strict) and ``/api/auth/logout`` (light) because
nginx ForwardAuth is bypassed for those paths (PR soft-auth).
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

_lock = Lock()
_buckets: dict[str, Deque[float]] = defaultdict(deque)


def _login_params() -> tuple[int, int]:
    # Defaults: stricter login window (anti brute-force).
    return (
        int(os.getenv("AUTH_LOGIN_RATE_LIMIT") or 8),
        int(os.getenv("AUTH_LOGIN_RATE_WINDOW_SEC") or 900),
    )


def _logout_params() -> tuple[int, int]:
    return (
        int(os.getenv("AUTH_LOGOUT_RATE_LIMIT") or 30),
        int(os.getenv("AUTH_LOGOUT_RATE_WINDOW_SEC") or 60),
    )


def _prune(q: Deque[float], window: int, now: float) -> None:
    cutoff = now - window
    while q and q[0] < cutoff:
        q.popleft()


def check_rate_limit(key: str, *, limit: int, window_sec: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_sec). Thread-safe sliding window."""
    if limit <= 0 or window_sec <= 0:
        return True, 0
    now = time.time()
    with _lock:
        q = _buckets[key]
        _prune(q, window_sec, now)
        if len(q) >= limit:
            retry = max(1, int(window_sec - (now - q[0])) + 1)
            return False, retry
        q.append(now)
        return True, 0


def client_ip(headers: dict | None, fallback: str = "unknown") -> str:
    if not headers:
        return fallback
    # Prefer edge-provided real IP (nginx X-Real-IP / X-Forwarded-For).
    for name in ("x-real-ip", "x-forwarded-for"):
        raw = headers.get(name) or headers.get(name.title())
        if not raw:
            continue
        # X-Forwarded-For may be a list; take first hop.
        return str(raw).split(",")[0].strip() or fallback
    return fallback


def login_rate_keys(ip: str, username: str | None) -> list[tuple[str, int, int]]:
    limit, window = _login_params()
    keys = [(f"login:ip:{ip}", limit, window)]
    user = str(username or "").strip().lower()
    if user:
        # Slightly stricter per-account to slow credential stuffing.
        keys.append((f"login:user:{user}", max(3, limit - 2), window))
    return keys


def logout_rate_keys(ip: str) -> list[tuple[str, int, int]]:
    limit, window = _logout_params()
    return [(f"logout:ip:{ip}", limit, window)]


def enforce(keys: list[tuple[str, int, int]]) -> int | None:
    """Apply all buckets; return retry_after if blocked, else None."""
    for key, limit, window in keys:
        ok, retry = check_rate_limit(key, limit=limit, window_sec=window)
        if not ok:
            return retry
    return None


def reset_for_tests() -> None:
    with _lock:
        _buckets.clear()
