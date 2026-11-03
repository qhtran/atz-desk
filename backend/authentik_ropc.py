"""Authentik OIDC Resource Owner Password Credentials (ROPC) — DEV only."""

from __future__ import annotations

import os
from typing import Any

import requests


class RopcConfigError(RuntimeError):
    """Thiếu env Authentik / Desk session."""


class RopcAuthError(RuntimeError):
    """Sai credentials hoặc Authentik từ chối grant."""


def ropc_configured() -> bool:
    return bool(
        (os.getenv("AUTHENTIK_TOKEN_URL") or "").strip()
        and (os.getenv("AUTHENTIK_CLIENT_ID") or "").strip()
        and (os.getenv("AUTHENTIK_CLIENT_SECRET") or "").strip()
    )


def _token_url() -> str:
    url = (os.getenv("AUTHENTIK_TOKEN_URL") or "").strip()
    if not url.startswith("https://"):
        raise RopcConfigError("AUTHENTIK_TOKEN_URL must be https://…")
    return url


def _userinfo_url() -> str:
    url = (os.getenv("AUTHENTIK_USERINFO_URL") or "").strip()
    if url:
        if not url.startswith("https://"):
            raise RopcConfigError("AUTHENTIK_USERINFO_URL must be https://…")
        return url
    # mặc định: cùng issuer path /application/o/userinfo/
    token = _token_url()
    if token.endswith("/token/"):
        return token[: -len("/token/")] + "/userinfo/"
    if token.endswith("/token"):
        return token[: -len("/token")] + "/userinfo"
    raise RopcConfigError("Set AUTHENTIK_USERINFO_URL explicitly")


def password_grant(username: str, password: str, *, timeout: float = 12.0) -> dict[str, Any]:
    """Đổi username/password → profile (username, email, name, uid, groups)."""
    if not ropc_configured():
        raise RopcConfigError("Authentik ROPC env not configured")
    user = str(username or "").strip()
    if not user or not password:
        raise RopcAuthError("username/password required")

    data = {
        "grant_type": "password",
        "username": user,
        "password": password,
        "client_id": os.environ["AUTHENTIK_CLIENT_ID"].strip(),
        "client_secret": os.environ["AUTHENTIK_CLIENT_SECRET"].strip(),
        "scope": (os.getenv("AUTHENTIK_SCOPE") or "openid profile email").strip(),
    }
    try:
        resp = requests.post(
            _token_url(),
            data=data,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"token endpoint unreachable: {exc}") from exc

    if resp.status_code in (400, 401):
        raise RopcAuthError("invalid credentials")
    if resp.status_code >= 400:
        raise RopcAuthError(f"token endpoint HTTP {resp.status_code}")

    try:
        token_payload = resp.json()
    except ValueError as exc:
        raise RopcAuthError("token endpoint returned non-JSON") from exc

    access = token_payload.get("access_token")
    if not access:
        raise RopcAuthError("no access_token in response")

    try:
        ui = requests.get(
            _userinfo_url(),
            headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"userinfo unreachable: {exc}") from exc

    if ui.status_code >= 400:
        raise RopcAuthError(f"userinfo HTTP {ui.status_code}")
    try:
        info = ui.json()
    except ValueError as exc:
        raise RopcAuthError("userinfo returned non-JSON") from exc

    preferred = str(info.get("preferred_username") or info.get("nickname") or user).strip()
    groups_raw = info.get("groups") or info.get("ak_groups") or []
    if isinstance(groups_raw, str):
        groups = [g.strip() for g in groups_raw.replace("|", ",").split(",") if g.strip()]
    elif isinstance(groups_raw, list):
        groups = [str(g).strip() for g in groups_raw if str(g).strip()]
    else:
        groups = []

    return {
        "username": preferred or user,
        "email": str(info.get("email") or ""),
        "name": str(info.get("name") or info.get("given_name") or preferred or user),
        "uid": str(info.get("sub") or ""),
        "groups": groups,
    }
