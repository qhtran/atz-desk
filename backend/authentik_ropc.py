"""Authentik headless login for Desk Session — DEV only.

Authentik 2026+ maps OAuth ``grant_type=password`` to App Password tokens.
Desk Welcome Gate uses the Flow Executor API. When the flow hits TOTP MFA,
password phase pauses and returns ``MfaRequired``; FE submits OTP to finish.
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import redis
import requests

from backend.redis_listener import REDIS_URL


class RopcConfigError(RuntimeError):
    """Thiếu env Authentik / Desk session."""


class RopcAuthError(RuntimeError):
    """Sai credentials hoặc Authentik từ chối đăng nhập."""


class MfaRequired(Exception):
    """Password OK — cần TOTP. ``mfa_token`` dùng cho bước OTP."""

    def __init__(self, mfa_token: str):
        super().__init__("mfa_required")
        self.mfa_token = mfa_token


_DEFAULT_FLOW_SLUG = "desk-ropc-authentication"
_MAX_FLOW_STEPS = 10
_MFA_KEY_PREFIX = "desk:mfa:"
_MFA_TTL_SEC = int(os.getenv("DESK_MFA_TTL_SEC") or 300)


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


def _export_cookies(session: requests.Session) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in session.cookies:
        out.append(
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain or "",
                "path": c.path or "/",
                "secure": bool(c.secure),
            }
        )
    return out


def _import_cookies(session: requests.Session, cookies: list[dict[str, Any]]) -> None:
    for c in cookies:
        session.cookies.set(
            str(c.get("name") or ""),
            str(c.get("value") or ""),
            domain=str(c.get("domain") or "") or None,
            path=str(c.get("path") or "/") or "/",
            secure=bool(c.get("secure")),
        )


def _redis() -> redis.Redis:
    # Timeout cứng — tránh login treo vô hạn nếu Redis/network kẹt.
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )


def _store_mfa_pending(session: requests.Session, flow_url: str) -> str:
    token = secrets.token_urlsafe(24)
    payload = {"flow_url": flow_url, "cookies": _export_cookies(session)}
    try:
        r = _redis()
        r.setex(f"{_MFA_KEY_PREFIX}{token}", _MFA_TTL_SEC, json.dumps(payload))
    except redis.RedisError as exc:
        raise RopcConfigError(f"Redis MFA store unavailable: {exc}") from exc
    return token


def _load_mfa_pending(token: str) -> tuple[str, list[dict[str, Any]]]:
    key = f"{_MFA_KEY_PREFIX}{(token or '').strip()}"
    try:
        r = _redis()
        raw = r.get(key)
    except redis.RedisError as exc:
        raise RopcConfigError(f"Redis MFA store unavailable: {exc}") from exc
    if not raw:
        raise RopcAuthError("mfa expired", "mfa_token missing or expired")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RopcAuthError("mfa expired", "corrupt mfa state") from exc
    flow_url = str(data.get("flow_url") or "")
    cookies = data.get("cookies")
    if not flow_url.startswith("https://") or not isinstance(cookies, list):
        raise RopcAuthError("mfa expired", "invalid mfa state")
    return flow_url, cookies


def _delete_mfa_pending(token: str) -> None:
    try:
        _redis().delete(f"{_MFA_KEY_PREFIX}{(token or '').strip()}")
    except redis.RedisError:
        pass


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


def _profile_from_session(
    session: requests.Session,
    *,
    flow_url: str,
    fallback_username: str,
    timeout: float,
) -> dict[str, Any]:
    me_url = _users_me_url(flow_url)
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

    preferred = str(info.get("username") or fallback_username).strip()
    groups = _normalize_groups(info.get("groups"))
    # Superuser Authentik → đủ quyền Admin Control Panel trên Desk
    if info.get("is_superuser") is True:
        if not any(g.lower() == "admin" for g in groups):
            groups = [*groups, "admin"]
    return {
        "username": preferred or fallback_username,
        "email": str(info.get("email") or ""),
        "name": str(info.get("name") or preferred or fallback_username),
        "uid": str(info.get("uid") or info.get("pk") or ""),
        "groups": groups,
        "is_superuser": bool(info.get("is_superuser")),
    }


def _finish_after_auth_stages(
    session: requests.Session,
    flow_url: str,
    payload: dict[str, Any],
    *,
    fallback_username: str,
    timeout: float,
    allow_mfa_pause: bool,
) -> dict[str, Any]:
    """Chạy từ stage hiện tại → user-login → profile. Có thể raise MfaRequired."""
    for _ in range(_MAX_FLOW_STEPS):
        component = str(payload.get("component") or "")
        err = _stage_errors(payload)

        if component == "ak-stage-authenticator-validate":
            if err:
                raise RopcAuthError("invalid otp", err)
            if allow_mfa_pause:
                token = _store_mfa_pending(session, flow_url)
                raise MfaRequired(token)
            raise RopcAuthError("invalid otp", "unexpected MFA stage")

        if err and component in {"ak-stage-identification", "ak-stage-password"}:
            raise RopcAuthError("invalid credentials", err)

        if component in {"xak-flow-redirect", "ak-stage-redirect"}:
            break

        if component == "ak-stage-user-login":
            payload = _post_flow(
                session,
                flow_url,
                {"component": "ak-stage-user-login", "remember_me": False},
                timeout=timeout,
            )
            continue

        if not component:
            break
        raise RopcAuthError(f"unexpected flow stage: {component}")

    return _profile_from_session(
        session,
        flow_url=flow_url,
        fallback_username=fallback_username,
        timeout=timeout,
    )


def password_grant(username: str, password: str, *, timeout: float = 12.0) -> dict[str, Any]:
    """Đổi username/password → profile. Raise ``MfaRequired`` nếu cần TOTP."""
    if not ropc_configured():
        raise RopcConfigError("Authentik flow env not configured")
    user = str(username or "").strip()
    if not user or not password:
        raise RopcAuthError("username/password required")

    flow_url = _flow_executor_url()
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

        if component == "ak-stage-authenticator-validate":
            return _finish_after_auth_stages(
                session,
                flow_url,
                payload,
                fallback_username=user,
                timeout=timeout,
                allow_mfa_pause=True,
            )

        if err and component in {
            "ak-stage-identification",
            "ak-stage-password",
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
            return _finish_after_auth_stages(
                session,
                flow_url,
                payload,
                fallback_username=user,
                timeout=timeout,
                allow_mfa_pause=True,
            )

        if not component:
            break
        raise RopcAuthError(f"unexpected flow stage: {component}")

    return _profile_from_session(
        session,
        flow_url=flow_url,
        fallback_username=user,
        timeout=timeout,
    )


def mfa_grant(mfa_token: str, code: str, *, timeout: float = 12.0) -> dict[str, Any]:
    """Hoàn tất login sau khi FE gửi mã TOTP."""
    if not ropc_configured():
        raise RopcConfigError("Authentik flow env not configured")
    otp = str(code or "").strip().replace(" ", "")
    if not mfa_token or not otp:
        raise RopcAuthError("invalid otp", "mfa_token/code required")
    if not otp.isdigit() or not (6 <= len(otp) <= 8):
        raise RopcAuthError("invalid otp", "OTP must be 6–8 digits")

    flow_url, cookies = _load_mfa_pending(mfa_token)
    session = requests.Session()
    _import_cookies(session, cookies)

    # Re-fetch current stage (should be authenticator-validate)
    try:
        cur = session.get(
            flow_url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RopcAuthError(f"flow endpoint unreachable: {exc}") from exc
    if cur.status_code >= 400:
        raise RopcAuthError("invalid otp", f"flow HTTP {cur.status_code}")
    payload = _json_or_empty(cur)
    if str(payload.get("component") or "") != "ak-stage-authenticator-validate":
        raise RopcAuthError("mfa expired", f"expected MFA stage, got {payload.get('component')}")

    payload = _post_flow(
        session,
        flow_url,
        {"component": "ak-stage-authenticator-validate", "code": otp},
        timeout=timeout,
    )
    err = _stage_errors(payload)
    if err or str(payload.get("component") or "") == "ak-stage-authenticator-validate":
        # Keep pending token so user can retry OTP within TTL
        raise RopcAuthError("invalid otp", err or "invalid otp")

    profile = _finish_after_auth_stages(
        session,
        flow_url,
        payload,
        fallback_username="",
        timeout=timeout,
        allow_mfa_pause=False,
    )
    _delete_mfa_pending(mfa_token)
    return profile
