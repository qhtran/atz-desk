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
_DEFAULT_LISTING_CSV = _ROOT / "config" / "exchange_listing.csv"


def _catalog_json_path() -> Path:
    return Path(os.getenv("MARKET_CATALOG_JSON", str(_DEFAULT_CATALOG_JSON)))


def _core_yaml_path() -> Path:
    return Path(os.getenv("PRICEBOARD_CORE_SYMBOLS", str(_DEFAULT_CORE_YAML)))


def _f3_yaml_path() -> Path:
    return Path(os.getenv("F3_THEMES_CONFIG", str(_DEFAULT_F3_YAML)))


def _listing_csv_path() -> Path:
    return Path(os.getenv("EXCHANGE_LISTING_CSV", str(_DEFAULT_LISTING_CSV)))


def clear_catalog_cache() -> None:
    load_market_catalog.cache_clear()
    load_core_symbol_set.cache_clear()
    load_exchange_listing_map.cache_clear()


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
def load_exchange_listing_map() -> dict[str, str]:
    """symbol → exchange from ``config/exchange_listing.csv`` (Core allocation source)."""
    path = _listing_csv_path()
    if not path.is_file():
        return {}
    try:
        import csv

        out: dict[str, str] = {}
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                sym = str(row.get("symbol") or "").strip().upper()
                ex = str(row.get("exchange") or "").strip().upper()
                if ex in ("HSX",):
                    ex = "HOSE"
                if ex.startswith("UPCO"):
                    ex = "UPCOM"
                if not sym or ex not in ("HOSE", "HNX", "UPCOM"):
                    continue
                out[sym] = ex
        return out
    except Exception:
        return {}


def resolve_listed_exchange(symbol: str) -> str:
    sym = str(symbol or "").strip().upper()
    hit = load_exchange_listing_map().get(sym)
    if hit:
        return hit
    return exchange_for_symbol(sym)


@lru_cache(maxsize=1)
def load_market_catalog() -> tuple[dict[str, dict[str, Any]], ...]:
    """Return tuple of catalog rows (stable for cache identity)."""
    core = load_core_symbol_set()
    overlay = _json_overlay()
    listing = load_exchange_listing_map()
    symbols: set[str] = set()
    symbols.update(VN30_SYMBOLS)
    symbols.update(HOSE_EXTRA_SYMBOLS)
    symbols.update(HNX_SYMBOLS)
    symbols.update(UPCOM_SYMBOLS)
    symbols.update(default_watchlist())
    symbols.update(_f3_symbols())
    symbols.update(overlay.keys())
    symbols.update(core)
    # Keep listing-backed names for Core HNX/UPCOM seats
    symbols.update(s for s, ex in listing.items() if s in core)

    rows: list[dict[str, Any]] = []
    for sym in sorted(symbols):
        ov = overlay.get(sym) or {}
        exchange = str(
            ov.get("exchange") or listing.get(sym) or exchange_for_symbol(sym)
        ).upper()
        if exchange == "HSX":
            exchange = "HOSE"
        if exchange.startswith("UPCO"):
            exchange = "UPCOM"
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


def _core_symbol_list_ordered() -> list[str]:
    """Ordered Top-N core symbols (YAML order); fallback default_watchlist."""
    path = _core_yaml_path()
    symbols: list[str] = []
    max_core = 240
    if path.is_file():
        try:
            import yaml

            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(doc, dict):
                if doc.get("max_core"):
                    max_core = max(50, min(400, int(doc["max_core"])))
                raw = doc.get("symbols")
                if isinstance(raw, list) and raw:
                    symbols = [str(s).strip().upper() for s in raw if str(s).strip()]
        except Exception:
            symbols = []
    if not symbols:
        symbols = list(default_watchlist())
    out: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= max_core:
            break
    return out


def list_core_catalog(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Full Top-N core rows for iBoard boot (Master Catalog + core YAML order)."""
    by_sym = catalog_index()
    ordered = _core_symbol_list_ordered()
    if limit is not None:
        ordered = ordered[: max(1, int(limit))]
    out: list[dict[str, Any]] = []
    for sym in ordered:
        row = by_sym.get(sym)
        if row:
            out.append(dict(row))
        else:
            out.append(
                {
                    "symbol": sym,
                    "exchange": resolve_listed_exchange(sym),
                    "name": "",
                    "in_core": True,
                }
            )
    return out


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
