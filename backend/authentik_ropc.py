"""Authentik headless login for Desk Session — DEV only.

Authentik 2026+ maps OAuth ``grant_type=password`` to **App Password tokens**,
not the user's account password. Desk Welcome Gate therefore authenticates via
the Flow Executor API (identification + password stage, no MFA flow).
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests


class RopcConfigError(RuntimeError):
    """Thiếu env Authentik / Desk session."""


class RopcAuthError(RuntimeError):
    """Sai credentials hoặc Authentik từ chối đăng nhập."""


_DEFAULT_FLOW_SLUG = "desk-ropc-authentication"
_MAX_FLOW_STEPS = 8


def _require_https(raw: str, *, name: str) -> str:
    url = (raw or "").strip()
    if not url.startswith("https://"):
        raise RopcConfigError(f"{name} must be https://…")
    return url


def _flow_executor_url() -> str:
    explicit = (os.getenv("AUTHENTIK_FLOW_URL") or "").strip()
    if explicit:
        url = _require_https(explicit, name="AUTHENTIK_FLOW_URL")
        return url if url.endswith("/") else url + "/"

    base = (os.getenv("AUTHENTIK_BASE_URL") or "").strip().rstrip("/")
    if not base:
        # Derive host from legacy TOKEN_URL if present
        token = (os.getenv("AUTHENTIK_TOKEN_URL") or "").strip()
        if token.startswith("https://"):
            parts = urlsplit(token)
            base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    if not base.startswith("https://"):
        raise RopcConfigError(
            "Set AUTHENTIK_FLOW_URL (preferred) or AUTHENTIK_BASE_URL / AUTHENTIK_TOKEN_URL"
        )
    slug = (os.getenv("AUTHENTIK_AUTH_FLOW_SLUG") or _DEFAULT_FLOW_SLUG).strip().strip("/")
    return f"{base}/api/v3/flows/executor/{slug}/"


def _users_me_url(flow_url: str) -> str:
    explicit = (os.getenv("AUTHENTIK_USERS_ME_URL") or "").strip()
    if explicit:
        return _require_https(explicit, name="AUTHENTIK_USERS_ME_URL").rstrip("/")
    parts = urlsplit(flow_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/v3/core/users/me/", "", ""))


def ropc_configured() -> bool:
    """True khi có đủ thông tin để gọi Flow Executor (không cần client secret)."""
    if (os.getenv("AUTHENTIK_FLOW_URL") or "").strip().startswith("https://"):
        return True
    if (os.getenv("AUTHENTIK_BASE_URL") or "").strip().startswith("https://"):
        return True
    token = (os.getenv("AUTHENTIK_TOKEN_URL") or "").strip()
    return token.startswith("https://")


def _json_or_empty(resp: requests.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _stage_errors(payload: dict[str, Any]) -> str:
    errs = payload.get("response_errors")
    if not isinstance(errs, dict) or not errs:
        return ""
    parts: list[str] = []
    for key, items in errs.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("string"):
                parts.append(f"{key}: {item.get('string')}")
            else:
                parts.append(f"{key}: {item}")
    return "; ".join(parts)


def _normalize_groups(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [g.strip() for g in raw.replace("|", ",").split(",") if g.strip()]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("group") or item.get("pk")
            if name is not None and str(name).strip():
                out.append(str(name).strip())
    return out


def _post_flow(
    session: requests.Session,
    flow_url: str,
    body: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    try:
        resp = session.post(
            flow_url,
            json=body,
            headers={"Accept": "application/json"},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"flow endpoint unreachable: {exc}") from exc

    # Authentik advances stages with 302 → same executor URL
    redirects = 0
    while resp.status_code in (301, 302, 303, 307, 308) and redirects < 5:
        loc = resp.headers.get("Location") or flow_url
        next_url = urljoin(flow_url, loc)
        try:
            resp = session.get(
                next_url,
                headers={"Accept": "application/json"},
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RopcAuthError(f"flow redirect unreachable: {exc}") from exc
        redirects += 1

    if resp.status_code >= 400:
        raise RopcAuthError(f"flow HTTP {resp.status_code}")
    return _json_or_empty(resp)


def password_grant(username: str, password: str, *, timeout: float = 12.0) -> dict[str, Any]:
    """Đổi username/password → profile qua Authentik Flow Executor."""
    if not ropc_configured():
        raise RopcConfigError("Authentik flow env not configured")
    user = str(username or "").strip()
    if not user or not password:
        raise RopcAuthError("username/password required")

    flow_url = _flow_executor_url()
    me_url = _users_me_url(flow_url)
    session = requests.Session()

    try:
        boot = session.get(
            flow_url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"flow endpoint unreachable: {exc}") from exc
    if boot.status_code >= 400:
        raise RopcAuthError(f"flow HTTP {boot.status_code}")

    payload = _json_or_empty(boot)
    submitted_password = False

    for _ in range(_MAX_FLOW_STEPS):
        component = str(payload.get("component") or "")
        err = _stage_errors(payload)
        if err and component in {
            "ak-stage-identification",
            "ak-stage-password",
            "ak-stage-authenticator-validate",
        }:
            raise RopcAuthError("invalid credentials", err)

        if component in {"xak-flow-redirect", "ak-stage-redirect"}:
            break

        if component == "ak-stage-identification":
            if submitted_password:
                raise RopcAuthError("invalid credentials", err or "identification rejected")
            payload = _post_flow(
                session,
                flow_url,
                {
                    "component": "ak-stage-identification",
                    "uid_field": user,
                    "password": password,
                },
                timeout=timeout,
            )
            submitted_password = True
            continue

        if component == "ak-stage-password":
            payload = _post_flow(
                session,
                flow_url,
                {"component": "ak-stage-password", "password": password},
                timeout=timeout,
            )
            submitted_password = True
            continue

        if component == "ak-stage-user-login":
            body: dict[str, Any] = {"component": "ak-stage-user-login", "remember_me": False}
            payload = _post_flow(session, flow_url, body, timeout=timeout)
            continue

        if component == "ak-stage-authenticator-validate":
            raise RopcAuthError(
                "invalid credentials",
                "MFA required — Desk flow must skip authenticator validation",
            )

        if not component:
            break
        raise RopcAuthError(f"unexpected flow stage: {component}")

    try:
        me_resp = session.get(
            me_url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"users/me unreachable: {exc}") from exc
    if me_resp.status_code >= 400:
        raise RopcAuthError("invalid credentials", f"users/me HTTP {me_resp.status_code}")

    me_body = _json_or_empty(me_resp)
    info = me_body.get("user") if isinstance(me_body.get("user"), dict) else me_body
    if not isinstance(info, dict) or not info.get("username"):
        raise RopcAuthError("invalid credentials", "no authenticated user")

    preferred = str(info.get("username") or user).strip()
    return {
        "username": preferred or user,
        "email": str(info.get("email") or ""),
        "name": str(info.get("name") or preferred or user),
        "uid": str(info.get("uid") or info.get("pk") or ""),
        "groups": _normalize_groups(info.get("groups")),
    }
