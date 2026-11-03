"""Desk account UX config — ForwardAuth URLs + admin groups (no Authentik API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _REPO_ROOT / "config" / "account.yaml"


def safe_https_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw.startswith("https://"):
        return ""
    return raw


def load_account_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load ``config/account.yaml`` → flat public fields for SPA /api/account/me."""
    target = Path(path or os.getenv("ACCOUNT_CONFIG") or _DEFAULT_PATH)
    block: dict[str, Any] = {}
    if target.is_file():
        try:
            doc = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
            raw = doc.get("account")
            if isinstance(raw, dict):
                block = raw
        except Exception:
            block = {}

    admin_groups_raw = block.get("admin_groups") or ["admin"]
    if isinstance(admin_groups_raw, str):
        admin_groups = [g.strip() for g in admin_groups_raw.split(",") if g.strip()]
    elif isinstance(admin_groups_raw, list):
        admin_groups = [str(g).strip() for g in admin_groups_raw if str(g).strip()]
    else:
        admin_groups = ["admin"]

    return {
        "enabled": bool(block.get("enabled", True)),
        "login_url": safe_https_url(block.get("login_url")),
        "logout_url": safe_https_url(block.get("logout_url")),
        "password_flow_url": safe_https_url(block.get("password_flow_url")),
        "mfa_flow_url": safe_https_url(block.get("mfa_flow_url")),
        "admin_groups": admin_groups,
    }
