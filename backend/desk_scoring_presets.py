"""Load Desk Scoring Matrix presets from YAML (isolated from SQLite rules)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "desk_scoring_presets.yaml"


def presets_config_path() -> Path:
    raw = (os.getenv("DESK_SCORING_PRESETS_PATH") or "").strip()
    return Path(raw) if raw else _DEFAULT_PATH


@lru_cache(maxsize=4)
def _load_doc(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"scoring presets not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("scoring presets YAML must be a mapping")
    profiles = raw.get("profiles") or {}
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("scoring presets: profiles required")
    return raw


def clear_presets_cache() -> None:
    _load_doc.cache_clear()


def list_presets(path: Path | None = None) -> dict[str, Any]:
    """Return catalog summary for SPA select."""
    doc = _load_doc(str(path or presets_config_path()))
    default_profile = str(doc.get("default_profile") or "default")
    items = []
    for key, prof in (doc.get("profiles") or {}).items():
        if not isinstance(prof, dict):
            continue
        rules = prof.get("rules") or []
        items.append(
            {
                "id": str(key),
                "label": str(prof.get("label") or key),
                "description": str(prof.get("description") or ""),
                "rule_count": len(rules) if isinstance(rules, list) else 0,
            }
        )
    if default_profile not in {i["id"] for i in items} and items:
        default_profile = items[0]["id"]
    return {
        "version": int(doc.get("version") or 1),
        "default_profile": default_profile,
        "items": items,
    }


def _normalize_rules(raw_rules: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw_rules, list):
        return out
    for raw in raw_rules:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("rule_code") or "").strip().upper()
        if not code:
            continue
        cond = raw.get("condition_json") or {}
        if not isinstance(cond, dict):
            continue
        out.append(
            {
                "rule_code": code,
                "category": str(raw.get("category") or "general"),
                "name": str(raw.get("name") or code),
                "weight": float(raw.get("weight") or 0),
                "condition_json": cond,
                "is_active": True,
            }
        )
    return out


def get_preset_rules(profile: str | None = None, path: Path | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Resolve profile id + rule list for evaluate. Raises KeyError if unknown."""
    doc = _load_doc(str(path or presets_config_path()))
    default_profile = str(doc.get("default_profile") or "default")
    key = str(profile or "").strip() or default_profile
    profiles = doc.get("profiles") or {}
    if key not in profiles:
        raise KeyError(key)
    prof = profiles[key] or {}
    if not isinstance(prof, dict):
        raise KeyError(key)
    rules = _normalize_rules(prof.get("rules"))
    if not rules:
        raise ValueError(f"preset {key!r} has no rules")
    return key, rules
