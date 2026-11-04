"""Master symbol catalog for Desk search / Quick Switcher (P0).

Sources (merged, deduped):
  1. ``config/market_catalog.json`` optional extensions (name, exchange overrides)
  2. ``config/sector_themes_f3.yaml`` theme symbols
  3. ``board_universe`` (VN30 / HOSE extra / HNX / UPCOM samples)
  4. Core flag from ``config/priceboard_core_symbols.yaml`` or ``default_watchlist()``
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.board_universe import (
    HNX_SYMBOLS,
    HOSE_EXTRA_SYMBOLS,
    UPCOM_SYMBOLS,
    VN30_SYMBOLS,
    default_watchlist,
    exchange_for_symbol,
)

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CATALOG_JSON = _ROOT / "config" / "market_catalog.json"
_DEFAULT_CORE_YAML = _ROOT / "config" / "priceboard_core_symbols.yaml"
_DEFAULT_F3_YAML = _ROOT / "config" / "sector_themes_f3.yaml"


def _catalog_json_path() -> Path:
    return Path(os.getenv("MARKET_CATALOG_JSON", str(_DEFAULT_CATALOG_JSON)))


def _core_yaml_path() -> Path:
    return Path(os.getenv("PRICEBOARD_CORE_SYMBOLS", str(_DEFAULT_CORE_YAML)))


def _f3_yaml_path() -> Path:
    return Path(os.getenv("F3_THEMES_CONFIG", str(_DEFAULT_F3_YAML)))


def clear_catalog_cache() -> None:
    load_market_catalog.cache_clear()
    load_core_symbol_set.cache_clear()


@lru_cache(maxsize=1)
def load_core_symbol_set() -> frozenset[str]:
    path = _core_yaml_path()
    symbols: list[str] = []
    if path.is_file():
        try:
            import yaml

            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            raw = doc.get("symbols") if isinstance(doc, dict) else None
            if isinstance(raw, list) and raw:
                symbols = [str(s).strip().upper() for s in raw if str(s).strip()]
        except Exception:
            symbols = []
    if not symbols:
        symbols = list(default_watchlist())
    # Cap soft — keep deterministic order
    max_core = 240
    if path.is_file():
        try:
            import yaml

            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(doc, dict) and doc.get("max_core"):
                max_core = max(50, min(400, int(doc["max_core"])))
        except Exception:
            pass
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= max_core:
            break
    return frozenset(out)


def _f3_symbols() -> set[str]:
    path = _f3_yaml_path()
    if not path.is_file():
        return set()
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    themes = doc.get("themes") if isinstance(doc, dict) else None
    if not isinstance(themes, dict):
        return set()
    out: set[str] = set()
    for meta in themes.values():
        if not isinstance(meta, dict):
            continue
        for s in meta.get("symbols") or []:
            sym = str(s).strip().upper()
            if sym:
                out.add(sym)
        for s in meta.get("whitelist") or []:
            sym = str(s).strip().upper()
            if sym:
                out.add(sym)
    return out


def _json_overlay() -> dict[str, dict[str, Any]]:
    path = _catalog_json_path()
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    items = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        sym = str(raw.get("symbol") or "").strip().upper()
        if not sym:
            continue
        out[sym] = raw
    return out


@lru_cache(maxsize=1)
def load_market_catalog() -> tuple[dict[str, dict[str, Any]], ...]:
    """Return tuple of catalog rows (stable for cache identity)."""
    core = load_core_symbol_set()
    overlay = _json_overlay()
    symbols: set[str] = set()
    symbols.update(VN30_SYMBOLS)
    symbols.update(HOSE_EXTRA_SYMBOLS)
    symbols.update(HNX_SYMBOLS)
    symbols.update(UPCOM_SYMBOLS)
    symbols.update(default_watchlist())
    symbols.update(_f3_symbols())
    symbols.update(overlay.keys())

    rows: list[dict[str, Any]] = []
    for sym in sorted(symbols):
        ov = overlay.get(sym) or {}
        exchange = str(ov.get("exchange") or exchange_for_symbol(sym)).upper()
        name = str(ov.get("name") or "").strip()
        rows.append(
            {
                "symbol": sym,
                "exchange": exchange if exchange in ("HOSE", "HNX", "UPCOM") else "HOSE",
                "name": name,
                "in_core": sym in core,
            }
        )
    return tuple(rows)


def catalog_index() -> dict[str, dict[str, Any]]:
    return {row["symbol"]: row for row in load_market_catalog()}


def search_catalog(query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    q = str(query or "").strip().upper()
    limit = max(1, min(50, int(limit or 12)))
    rows = list(load_market_catalog())
    if not q:
        # Prefer core symbols when browsing empty query
        core_first = [r for r in rows if r.get("in_core")]
        rest = [r for r in rows if not r.get("in_core")]
        ordered = core_first + rest
        return ordered[:limit]

    scored: list[tuple[int, int, str, dict[str, Any]]] = []
    for row in rows:
        sym = str(row["symbol"])
        name = str(row.get("name") or "").upper()
        if q not in sym and q not in name:
            continue
        if sym.startswith(q):
            rank = 0
        elif name.startswith(q):
            rank = 1
        else:
            rank = 2
        # Core slightly preferred within same rank
        rank_tie = 0 if row.get("in_core") else 1
        scored.append((rank, rank_tie, sym, row))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[3] for t in scored[:limit]]


def get_catalog_symbol(symbol: str) -> dict[str, Any] | None:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    return catalog_index().get(sym)
