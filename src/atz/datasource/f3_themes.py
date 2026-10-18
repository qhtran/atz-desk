"""Đọc seed danh mục ngành F3 (config/sector_themes_f3.yaml) — chỉ đọc, không sửa list mentor."""

from __future__ import annotations

from pathlib import Path

import yaml

from storage.paths import repo_root

DEFAULT_THEMES_PATH = repo_root() / "config" / "sector_themes_f3.yaml"


def load_f3_sector_themes(path: Path | None = None) -> list[dict]:
    """Trả list {id, name, symbols, kind: 'f3'} — file thiếu/lỗi → []."""
    target = path or DEFAULT_THEMES_PATH
    if not target.exists():
        return []
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    themes = raw.get("themes") or {}
    result: list[dict] = []
    for key, item in themes.items():
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or key).strip()
        symbols = []
        seen: set[str] = set()
        for symbol in item.get("symbols") or []:
            code = str(symbol).strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            symbols.append(code)
        if not label or not symbols:
            continue
        result.append(
            {
                "id": f"f3:{key}",
                "name": label,
                "symbols": symbols,
                "kind": "f3",
            }
        )
    return result
