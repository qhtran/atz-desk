"""Batch OHLCV filters for iBoard «Tín hiệu ngày» (subset, một bảng)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from backend.board_universe import symbols_for_market_tab
from backend.filters import BATCH_EVALUATORS, NATIVE_BATCH_FILTERS
from backend.filters._types import BatchSignal
from backend.portfolio_f3 import _ensure_legacy_path, _legacy_atz_root, load_symbol_bars

ALLOWED_FILTERS = frozenset(
    {
        "rsi",
        "macd",
        "ma",
        "candle",
        "volume",
        "foreign",
        "advisor",
        "bollinger",
        "adx",
        "atr",
        "rs_index",
        "breakout_52w",
        "stochastic",
        "foreign_streak",
        "liquidity",
        "market_regime",
    }
)

from zoneinfo import ZoneInfo

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_scan_cache: dict[tuple[Any, ...], tuple[str, list[dict[str, Any]], int, int]] = {}


def _trading_day_key() -> str:
    return datetime.now(_VN_TZ).strftime("%Y-%m-%d")


def clear_daily_scan_cache() -> None:
    """Xóa cache quét (dùng trong test / sau cập nhật OHLCV)."""
    _scan_cache.clear()


@lru_cache(maxsize=1)
def _filter_registry() -> dict[str, Any]:
    _ensure_legacy_path()
    root = _legacy_atz_root()
    filters_dir = root / "filters"
    if not filters_dir.is_dir():
        return {}
    from filters import load_registry

    reg = load_registry(filters_dir)
    plugin_filters = ALLOWED_FILTERS - {"advisor"} - NATIVE_BATCH_FILTERS
    return {k: v for k, v in reg.items() if k in plugin_filters}


def _advisor_scoring_bundle(username: str | None = None):
    """Native vectorized advisor + risk profile (Phase 3A)."""
    from backend.core.trading_config import risk_meta_for_user, scoring_config_for_user
    from backend.engine.advisor_score import hits_from_panels, score_frame_from_panels

    scoring = scoring_config_for_user(username)
    meta = risk_meta_for_user(username)
    return scoring, meta, hits_from_panels, score_frame_from_panels


def _normalize_filter_names(filter_name: str, filters: list[str] | None) -> list[str]:
    if filters:
        raw = [str(f).strip().lower() for f in filters if str(f).strip()]
    else:
        raw = [str(filter_name or "rsi").strip().lower()]
    out: list[str] = []
    for name in raw:
        if name not in ALLOWED_FILTERS or name in out:
            continue
        out.append(name)
    return out


def load_universe_panels(
    universe: list[str],
    bars_dir: Path | None,
) -> tuple[dict[str, pd.DataFrame], int]:
    """Load OHLCV panels once (I/O only); returns (symbol -> bars, scanned count)."""
    panels: dict[str, pd.DataFrame] = {}
    scanned = 0
    for sym in universe:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None or bars.empty:
            continue
        scanned += 1
        panels[str(sym).upper()] = bars
    return panels, scanned


def _batch_signal_for_filter(
    name: str,
    panels: dict[str, pd.DataFrame],
    index_bars: pd.DataFrame | None,
) -> dict[str, BatchSignal]:
    if name in NATIVE_BATCH_FILTERS:
        fn = BATCH_EVALUATORS[name]
        return fn(panels)
    registry = _filter_registry()
    module = registry.get(name)
    out: dict[str, BatchSignal] = {}
    if module is None:
        return out
    params = _plugin_params(name, index_bars)
    for sym, bars in panels.items():
        try:
            result = module.evaluate(bars, params)
        except Exception:
            out[sym] = BatchSignal(False, "giu", "", None)
            continue
        out[sym] = BatchSignal(
            bool(getattr(result, "matched", False)),
            str(getattr(result, "signal_type", "giu") or "giu"),
            str(getattr(result, "reason", "") or ""),
            getattr(result, "details", None),
        )
    return out


def _advisor_hit(
    bars: pd.DataFrame,
    buy_min_total: float | None,
    *,
    username: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    scoring, meta, _, score_frame = _advisor_scoring_bundle(username)
    floor = float(buy_min_total if buy_min_total is not None else scoring.get("buy_min_total", 65))
    try:
        frame = score_frame({"TMP": bars}, scoring)
    except Exception:
        return False, None
    if frame.empty or pd.isna(frame.iloc[0]["score"]):
        return False, None
    row = frame.iloc[0]
    total = float(row["score"])
    if total < floor:
        return False, None
    return True, {
        "signal_type": str(row["recommendation"]),
        "reason": str(row["reason"]),
        "total": total,
        "score": total,
        "trend": float(row["trend"]),
        "flow": float(row["flow"]),
        "short_term": float(row["short_term"]),
        "risk_meta": meta,
    }


def _plugin_params(name: str, index_bars: pd.DataFrame | None) -> dict[str, Any] | None:
    if name in {"rs_index", "market_regime"}:
        return {"index_bars": index_bars}
    return None


def _index_bars_for_scan(names: list[str], bars_dir: Path | None) -> pd.DataFrame | None:
    if "rs_index" in names or "market_regime" in names:
        return load_symbol_bars("VNINDEX", bars_dir)
    return None


def _market_regime_blocks(names: list[str], combine_or: bool, index_bars: pd.DataFrame | None) -> bool:
    """AND + market_regime: nếu VNINDEX không uptrend thì không quét mã."""
    if combine_or or "market_regime" not in names or len(names) == 1:
        return False
    registry = _filter_registry()
    mod = registry.get("market_regime")
    if mod is None or index_bars is None or index_bars.empty:
        return True
    try:
        result = mod.evaluate(
            index_bars.iloc[:1],
            {"index_bars": index_bars},
        )
    except Exception:
        return True
    return not getattr(result, "matched", False) or getattr(result, "signal_type", "") != "mua"


def _combine_panel_hits(
    panels: dict[str, pd.DataFrame],
    names: list[str],
    combine_or: bool,
    per_filter: dict[str, dict[str, BatchSignal]],
    buy_min_total: float | None,
    *,
    username: str | None = None,
) -> list[dict[str, Any]]:
    advisor_by_sym: dict[str, dict[str, Any]] = {}
    if "advisor" in names:
        scoring, meta, hits_from_panels, _ = _advisor_scoring_bundle(username)
        floor = float(
            buy_min_total if buy_min_total is not None else scoring.get("buy_min_total", 65)
        )
        for row in hits_from_panels(panels, scoring, buy_min_total=floor, risk_meta=meta):
            advisor_by_sym[str(row["symbol"]).upper()] = row

    hits: list[dict[str, Any]] = []
    for sym in sorted(panels.keys()):
        matched_names: list[str] = []
        reasons: list[str] = []
        advisor_extra: dict[str, Any] | None = None
        for name in names:
            if name == "advisor":
                extra = advisor_by_sym.get(str(sym).upper())
                if extra:
                    matched_names.append("advisor")
                    advisor_extra = extra
                    if extra.get("reason"):
                        reasons.append(f"advisor: {extra['reason']}")
                elif not combine_or:
                    break
                continue
            sig = per_filter.get(name, {}).get(sym)
            if sig is None:
                if not combine_or:
                    matched_names = []
                    break
                continue
            if sig.matched:
                matched_names.append(name)
                if sig.reason:
                    reasons.append(f"{name}: {sig.reason}")
            elif not combine_or:
                matched_names = []
                break
        if combine_or:
            if not matched_names:
                continue
        elif len(matched_names) != len(names):
            continue
        row: dict[str, Any] = {
            "symbol": sym.upper(),
            "filter": ",".join(matched_names),
            "filters": list(matched_names),
            "signal_type": "mua",
            "reason": "; ".join(reasons),
        }
        if advisor_extra:
            row.update(advisor_extra)
            row["signal_type"] = advisor_extra.get("signal_type", row["signal_type"])
        elif matched_names:
            first = matched_names[0]
            sig0 = per_filter.get(first, {}).get(sym)
            if sig0 is not None and sig0.matched:
                row["signal_type"] = sig0.signal_type or "mua"
        hits.append(row)
    if "advisor" in names:
        hits.sort(key=lambda row: float(row.get("total") or 0), reverse=True)
    return hits


def scan_advisor_scores(
    *,
    market: str = "HOSE",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
    username: str | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét cố vấn 0–100 (vectorized); hits có score >= ngưỡng."""
    scoring, meta, hits_from_panels, _ = _advisor_scoring_bundle(username)
    floor = float(buy_min_total if buy_min_total is not None else scoring.get("buy_min_total", 65))
    universe = symbols or symbols_for_market_tab(market)
    panels, scanned = load_universe_panels(universe, bars_dir)
    hits = hits_from_panels(
        panels,
        scoring,
        buy_min_total=floor,
        risk_meta=meta,
    )
    return hits, scanned, len(hits)


def scan_daily_signals(
    *,
    market: str = "HOSE",
    filter_name: str = "rsi",
    filters: list[str] | None = None,
    combine: str = "and",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
    use_cache: bool = True,
    username: str | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét mã; trả (hits, scanned, matched_count). Hỗ trợ nhiều filter (AND/OR)."""
    names = _normalize_filter_names(filter_name, filters)
    if not names:
        return [], 0, 0
    combine_or = str(combine or "and").strip().lower() == "or"
    day = _trading_day_key()
    sym_key: tuple[str, ...] | None = None
    if symbols is not None:
        sym_key = tuple(sorted(str(s).upper() for s in symbols))
    names_key = tuple(names)
    cache_key = (market.upper(), names_key, combine_or, buy_min_total, sym_key, username or "")
    if use_cache:
        cached = _scan_cache.get(cache_key)
        if cached and cached[0] == day:
            hits, scanned, matched = cached[1], cached[2], cached[3]
            return list(hits), scanned, matched

    if names == ["advisor"]:
        hits, scanned, matched = scan_advisor_scores(
            market=market,
            symbols=symbols,
            bars_dir=bars_dir,
            buy_min_total=buy_min_total,
            username=username,
        )
        if use_cache:
            _scan_cache[cache_key] = (day, hits, scanned, matched)
        return hits, scanned, matched

    index_bars = _index_bars_for_scan(names, bars_dir)
    if _market_regime_blocks(names, combine_or, index_bars):
        return [], 0, 0

    universe = symbols or symbols_for_market_tab(market)
    panels, scanned = load_universe_panels(universe, bars_dir)
    if not panels:
        return [], 0, 0

    per_filter: dict[str, dict[str, BatchSignal]] = {}
    for name in names:
        if name == "advisor":
            continue
        per_filter[name] = _batch_signal_for_filter(name, panels, index_bars)

    hits = _combine_panel_hits(
        panels,
        names,
        combine_or,
        per_filter,
        buy_min_total,
        username=username,
    )
    matched = len(hits)
    if use_cache:
        _scan_cache[cache_key] = (day, hits, scanned, matched)
    return hits, scanned, matched


def hit_symbols(
    *,
    market: str = "HOSE",
    filter_name: str = "rsi",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
) -> set[str]:
    rows, _, _ = scan_daily_signals(
        market=market,
        filter_name=filter_name,
        symbols=symbols,
        bars_dir=bars_dir,
    )
    return {str(r["symbol"]).upper() for r in rows}
