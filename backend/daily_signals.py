"""Batch OHLCV filters for iBoard «Tín hiệu ngày» (subset, một bảng)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from backend.board_universe import symbols_for_market_tab
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
    }
)

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
    plugin_filters = ALLOWED_FILTERS - {"advisor"}
    return {k: v for k, v in reg.items() if k in plugin_filters}


@lru_cache(maxsize=1)
def _advisor_engine():
    _ensure_legacy_path()
    from engine.advisor_score import compute_advisor_score, load_advisor_config

    return compute_advisor_score, load_advisor_config


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


def _advisor_hit(bars: pd.DataFrame, buy_min_total: float | None) -> tuple[bool, dict[str, Any] | None]:
    compute, load_cfg = _advisor_engine()
    cfg = load_cfg()
    th = cfg["thresholds"]
    floor = float(buy_min_total if buy_min_total is not None else th["buy_min_total"])
    params = {
        "thresholds": {
            "buy_min_total": floor,
            "sell_max_total": float(th["sell_max_total"]),
        },
    }
    try:
        score = compute(bars, params)
    except Exception:
        return False, None
    if score.total is None or float(score.total) < floor:
        return False, None
    return True, {
        "signal_type": score.recommendation,
        "reason": score.reason,
        "total": score.total,
        "trend": score.pillars["trend"]["points"],
        "flow": score.pillars["flow"]["points"],
        "short_term": score.pillars["short_term"]["points"],
    }


def _plugin_params(name: str, index_bars: pd.DataFrame | None) -> dict[str, Any] | None:
    if name == "rs_index":
        return {"index_bars": index_bars}
    return None


def scan_advisor_scores(
    *,
    market: str = "HOSE",
    symbols: list[str] | None = None,
    bars_dir: Path | None = None,
    buy_min_total: float | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Quét cố vấn 0–100; hits có total >= ngưỡng, sắp theo điểm giảm dần."""
    compute, load_cfg = _advisor_engine()
    cfg = load_cfg()
    th = cfg["thresholds"]
    floor = float(buy_min_total if buy_min_total is not None else th["buy_min_total"])
    params = {
        "thresholds": {
            "buy_min_total": floor,
            "sell_max_total": float(th["sell_max_total"]),
        },
    }
    universe = symbols or symbols_for_market_tab(market)
    hits: list[dict[str, Any]] = []
    scanned = 0
    for sym in universe:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None or bars.empty:
            continue
        scanned += 1
        try:
            score = compute(bars, params)
        except Exception:
            continue
        if score.total is None or float(score.total) < floor:
            continue
        hits.append(
            {
                "symbol": sym.upper(),
                "filter": "advisor",
                "signal_type": score.recommendation,
                "reason": score.reason,
                "total": score.total,
                "trend": score.pillars["trend"]["points"],
                "flow": score.pillars["flow"]["points"],
                "short_term": score.pillars["short_term"]["points"],
            }
        )
    hits.sort(key=lambda row: float(row["total"]), reverse=True)
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
    cache_key = (market.upper(), names_key, combine_or, buy_min_total, sym_key)
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
        )
        if use_cache:
            _scan_cache[cache_key] = (day, hits, scanned, matched)
        return hits, scanned, matched

    registry = _filter_registry()
    index_bars = load_symbol_bars("VNINDEX", bars_dir) if "rs_index" in names else None
    universe = symbols or symbols_for_market_tab(market)
    hits: list[dict[str, Any]] = []
    scanned = 0
    for sym in universe:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None or bars.empty:
            continue
        scanned += 1
        matched_names: list[str] = []
        reasons: list[str] = []
        advisor_extra: dict[str, Any] | None = None
        failed_and = False
        for name in names:
            if name == "advisor":
                ok, extra = _advisor_hit(bars, buy_min_total)
                if ok:
                    matched_names.append("advisor")
                    advisor_extra = extra
                    if extra and extra.get("reason"):
                        reasons.append(f"advisor: {extra['reason']}")
                elif not combine_or:
                    failed_and = True
                    break
                continue
            module = registry.get(name)
            if module is None:
                if not combine_or:
                    failed_and = True
                    break
                continue
            try:
                result = module.evaluate(bars, _plugin_params(name, index_bars))
            except Exception:
                if not combine_or:
                    failed_and = True
                    break
                continue
            if getattr(result, "matched", False):
                matched_names.append(name)
                reason = getattr(result, "reason", "")
                if reason:
                    reasons.append(f"{name}: {reason}")
            elif not combine_or:
                failed_and = True
                break
        if failed_and:
            continue
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
            mod = registry.get(first)
            if mod is not None:
                try:
                    r0 = mod.evaluate(bars, _plugin_params(first, index_bars))
                    row["signal_type"] = getattr(r0, "signal_type", "mua")
                except Exception:
                    pass
        hits.append(row)
    if "advisor" in names:
        hits.sort(key=lambda row: float(row.get("total") or 0), reverse=True)
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
