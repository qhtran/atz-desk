"""Priceboard SPA debug overlay config (dev.atz.vn)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from backend.observability import ERR_PB_CONFIG, log, setup

setup("api")
_COMPONENT = "api"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _REPO_ROOT / "config" / "debug_overlay.yaml"
_STORAGE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _env_tri_state(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("0", "false", "off", "no"):
        return False
    if raw in ("1", "true", "on", "yes"):
        return True
    return None


def _load_yaml_block(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        log(
            _COMPONENT,
            "DEBUG-UI-CONFIG",
            "debug_overlay yaml unreadable",
            error_code=ERR_PB_CONFIG,
            exc=exc,
            path=str(path),
        )
        return {}
    block = doc.get("debug_overlay")
    return block if isinstance(block, dict) else {}


def load_priceboard_debug_config(path: Path | str | None = None) -> dict[str, Any]:
    """Config for GET /api/debug-ui/config (priceboard surface only)."""
    path = Path(path or os.getenv("DEBUG_OVERLAY_CONFIG") or _DEFAULT_PATH)
    block = _load_yaml_block(path)

    global_on = bool(block.get("enabled", False))
    surfaces = block.get("surfaces") if isinstance(block.get("surfaces"), dict) else {}
    pb = surfaces.get("priceboard") if isinstance(surfaces.get("priceboard"), dict) else {}

    pb_enabled = bool(pb.get("enabled", True))
    inspect = bool(pb.get("inspect", True))
    catalog = str(pb.get("catalog") or "ui_catalog.json").strip() or "ui_catalog.json"

    storage_key = str(block.get("priceboard_storage_key") or pb.get("storage_key") or "pb-dbg-on").strip()
    if not _STORAGE_RE.match(storage_key):
        storage_key = "pb-dbg-on"

    enabled = global_on and pb_enabled
    env_pb = _env_tri_state("PB_DEBUG_UI")
    if env_pb is not None:
        enabled = env_pb

    return {
        "enabled": enabled,
        "storageKey": storage_key,
        "inspect": inspect,
        "catalogUrl": f"/static/{catalog.lstrip('/')}",
    }


def public_debug_ui_config() -> dict[str, Any]:
    """Safe JSON for browser bootstrap (no secrets)."""
    cfg = load_priceboard_debug_config()
    return {
        "enabled": cfg["enabled"],
        "storageKey": cfg["storageKey"],
        "inspect": cfg["inspect"],
        "catalogUrl": cfg["catalogUrl"],
    }
