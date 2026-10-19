"""REST auth v3 → accessToken cho WebSocket."""
from __future__ import annotations

import time

import requests

from ingestion.index.providers import _ssi_token


def fetch_token(auth_url: str, api_key: str, api_secret: str, timeout: float = 20) -> tuple[str, float]:
    r = requests.post(
        auth_url,
        json={"apiKey": api_key, "apiSecret": api_secret},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    tok = _ssi_token(body)
    if not tok:
        raise RuntimeError(f"SSI auth no token status={body.get('status')} msg={body.get('message')}")
    exp = body.get("expiresAt")
    try:
        exp_ts = float(exp) if exp is not None else time.time() + 6 * 3600
    except (TypeError, ValueError):
        exp_ts = time.time() + 6 * 3600
    return tok, max(time.time() + 60, exp_ts - 60)
