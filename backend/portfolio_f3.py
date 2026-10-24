"""F3 daily alerts for dev SPA — wraps analysis.f3_alerts + sector themes YAML."""

from __future__ import annotations

import os
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from backend.portfolio_quotes import DEFAULT_BARS_DIR, normalize_symbols

F3_THEMES_PATH = Path(
    os.getenv("F3_THEMES_CONFIG", Path(__file__).resolve().parent.parent / "config" / "sector_themes_f3.yaml")
)
OHLCV_DIR = Path(os.getenv("OHLCV_BARS_DIR", str(DEFAULT_BARS_DIR)))

# (symbol, session_iso) -> alert text
_f3_cache: dict[tuple[str, str], str] = {}


def _legacy_atz_root() -> Path:
    root = Path(__file__).resolve().parent.parent
    docker_pkg = root / "atz_pkg"
    src_pkg = root / "src" / "atz"
    if docker_pkg.is_dir() and (docker_pkg / "analysis" / "f3_alerts.py").is_file():
        return docker_pkg
    return src_pkg


def _ensure_legacy_path() -> None:
    pkg = str(_legacy_atz_root())
    if pkg not in sys.path:
        sys.path.insert(0, pkg)


@lru_cache(maxsize=1)
def _alert_column_fn():
    _ensure_legacy_path()
    from analysis.f3_alerts import alert_column_for_bars

    return alert_column_for_bars


def load_f3_sector_themes(path: Path | None = None) -> list[dict]:
    """Parity datasource.f3_themes.load_f3_sector_themes."""
    target = path or F3_THEMES_PATH
    if not target.is_file():
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
        symbols: list[str] = []
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


def load_symbol_bars(symbol: str, bars_dir: Path | None = None) -> pd.DataFrame | None:
    root = bars_dir or OHLCV_DIR
    path = root / f"{symbol.strip().upper()}.csv"
    if not path.is_file():
        return None
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError):
        return None
    if frame is None or frame.empty:
        return None
    return frame


def f3_alert_for_symbol(
    symbol: str,
    *,
    bars_dir: Path | None = None,
    session_date: date | None = None,
    use_cache: bool = True,
) -> str:
    sym = symbol.strip().upper()
    if not sym:
        return "—"
    day = session_date or date.today()
    cache_key = (sym, day.isoformat())
    if use_cache and cache_key in _f3_cache:
        return _f3_cache[cache_key]
    bars = load_symbol_bars(sym, bars_dir)
    alert_column = _alert_column_fn()
    text = alert_column(sym, bars, session_date=day)
    if use_cache:
        _f3_cache[cache_key] = text
    return text


def batch_f3_alerts(
    symbols: list[str],
    *,
    bars_dir: Path | None = None,
    session_date: date | None = None,
) -> dict[str, str]:
    syms = normalize_symbols(symbols)
    out: dict[str, str] = {}
    for sym in syms:
        out[sym] = f3_alert_for_symbol(sym, bars_dir=bars_dir, session_date=session_date)
    return out


def combine_f3_intraday_alert(f3_text: str | None, intraday_text: str | None) -> str:
    """Q1 hybrid — cố định: F3 (ngày) trước, intraday sau."""
    parts: list[str] = []
    if f3_text and f3_text.strip() and f3_text.strip() != "—":
        parts.append(f3_text.strip())
    if intraday_text and intraday_text.strip() not in ("—", "Chưa có giá"):
        parts.append(intraday_text.strip())
    return " · ".join(parts) if parts else "—"
