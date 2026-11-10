"""Runtime auth policy: session TTL + MFA remember (Admin overlay + env)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.admin_config_store import DEFAULT_OVERLAY, _read_overlay

# 7 ngày — yêu cầu Unified Login / Desk Session persistence.
DEFAULT_SESSION_TTL_SEC = 7 * 24 * 3600
DEFAULT_MFA_REMEMBER_SEC = 7 * 24 * 3600
MIN_TTL_SEC = 3600
MAX_TTL_SEC = 30 * 24 * 3600


def _clamp_ttl(raw: Any, default: int) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return max(MIN_TTL_SEC, min(MAX_TTL_SEC, n))


def _auth_overlay(overlay_path: Path | None = None) -> dict[str, Any]:
    overlay = _read_overlay(overlay_path or DEFAULT_OVERLAY)
    block = overlay.get("auth")
    return block if isinstance(block, dict) else {}


def session_ttl_sec(overlay_path: Path | None = None) -> int:
    """Cookie + signed desk session exp."""
    block = _auth_overlay(overlay_path)
    if block.get("session_ttl_sec") is not None:
        return _clamp_ttl(block.get("session_ttl_sec"), DEFAULT_SESSION_TTL_SEC)
    return _clamp_ttl(os.getenv("DESK_SESSION_TTL_SEC"), DEFAULT_SESSION_TTL_SEC)


def mfa_remember_enabled(overlay_path: Path | None = None) -> bool:
    block = _auth_overlay(overlay_path)
    if "mfa_remember_enabled" in block:
        return bool(block.get("mfa_remember_enabled"))
    flag = (os.getenv("DESK_MFA_REMEMBER") or "1").strip().lower()
    return flag not in ("0", "false", "off", "no")


def mfa_remember_sec(overlay_path: Path | None = None) -> int:
    if not mfa_remember_enabled(overlay_path):
        return 0
    block = _auth_overlay(overlay_path)
    if block.get("mfa_remember_sec") is not None:
        return _clamp_ttl(block.get("mfa_remember_sec"), DEFAULT_MFA_REMEMBER_SEC)
    return _clamp_ttl(os.getenv("DESK_MFA_REMEMBER_SEC"), DEFAULT_MFA_REMEMBER_SEC)


def effective_auth_policy(overlay_path: Path | None = None) -> dict[str, Any]:
    return {
        "session_ttl_sec": session_ttl_sec(overlay_path),
        "mfa_remember_enabled": mfa_remember_enabled(overlay_path),
        "mfa_remember_sec": mfa_remember_sec(overlay_path),
        "defaults": {
            "session_ttl_sec": DEFAULT_SESSION_TTL_SEC,
            "mfa_remember_sec": DEFAULT_MFA_REMEMBER_SEC,
            "mfa_remember_enabled": True,
        },
    }


def sanitize_auth_patch(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    if "session_ttl_sec" in raw and raw.get("session_ttl_sec") is not None:
        out["session_ttl_sec"] = _clamp_ttl(raw.get("session_ttl_sec"), DEFAULT_SESSION_TTL_SEC)
    if "mfa_remember_sec" in raw and raw.get("mfa_remember_sec") is not None:
        out["mfa_remember_sec"] = _clamp_ttl(raw.get("mfa_remember_sec"), DEFAULT_MFA_REMEMBER_SEC)
    if "mfa_remember_enabled" in raw:
        out["mfa_remember_enabled"] = bool(raw.get("mfa_remember_enabled"))
    return out
