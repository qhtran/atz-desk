"""Chạy filter đang bật và composite của user trên các khung nến."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from analysis.technical import enrich
from engine.composite import evaluate_composite
from filters import load_registry
from filters.base import SignalResult
from storage.repository import (
    list_composite_rules,
    list_filter_configs,
    record_signal,
    save_market_bar,
)

_INDICATORS = ("MA20", "MA50", "RSI", "MACD", "MACD_HIST")


def bar_date(bars: pd.DataFrame) -> str:
    if "time" not in bars.columns:
        raise ValueError("thiếu cột time")
    return pd.to_datetime(bars["time"].iloc[-1]).date().isoformat()


def _indicators(bars: pd.DataFrame) -> dict[str, float]:
    needed = {"open", "high", "low", "close", "volume"}
    if len(bars) < 20 or not needed.issubset(bars.columns):
        return {}
    work = enrich(bars)
    last = work.iloc[-1]
    found: dict[str, float] = {}
    for key in _INDICATORS:
        value = last[key]
        if pd.notna(value):
            found[key] = round(float(value), 4)
    return found


def _cache_bar(conn: sqlite3.Connection, symbol: str, bars: pd.DataFrame, date: str) -> None:
    last = bars.iloc[-1]
    save_market_bar(
        conn,
        symbol,
        "D",
        date,
        float(last["open"]),
        float(last["high"]),
        float(last["low"]),
        float(last["close"]),
        float(last["volume"]),
        _indicators(bars),
    )


def _remember(
    conn: sqlite3.Connection,
    user_id: int,
    symbol: str,
    name: str,
    date: str,
    result: SignalResult,
    price: float,
) -> tuple[int | None, bool]:
    if not result.matched:
        return None, False
    details = dict(result.details)
    details["reason"] = result.reason
    return record_signal(conn, user_id, symbol, name, result.signal_type, date, details, price)


def run_frames(
    conn: sqlite3.Connection,
    user_id: int,
    frames: dict[str, pd.DataFrame],
    index_bars: pd.DataFrame | None = None,
    configs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Chạy các khung đã có trong bộ nhớ. Khớp thì ghi signal_history, luôn ghi cache nến cuối."""
    modules = load_registry()
    if configs is None:
        configs = [row for row in list_filter_configs(conn, user_id) if row["enabled"]]
    rules = list_composite_rules(conn, str(user_id))
    reports: list[dict[str, Any]] = []
    for symbol, bars in frames.items():
        date = bar_date(bars)
        price = float(bars["close"].iloc[-1])
        _cache_bar(conn, symbol, bars, date)
        jobs: list[tuple[str, SignalResult]] = []
        for row in configs:
            module = modules.get(row["filter_name"])
            if module is None:
                continue
            jobs.append((row["filter_name"], module.evaluate(bars, row.get("parameters") or {})))
        for rule in rules:
            jobs.append((rule["name"], evaluate_composite(rule["definition"], bars, index_bars, modules)))
        for name, result in jobs:
            signal_id, created = _remember(conn, user_id, symbol, name, date, result, price)
            reports.append(
                {
                    "symbol": symbol.upper(),
                    "filter_name": name,
                    "bar_date": date,
                    "matched": result.matched,
                    "signal_type": result.signal_type,
                    "reason": result.reason,
                    "price": price,
                    "signal_id": signal_id,
                    "created": created,
                }
            )
    return reports


def load_symbol_csv(bars_dir: Path, symbol: str) -> pd.DataFrame | None:
    path = bars_dir / f"{symbol.strip().upper()}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def run_symbols(
    conn: sqlite3.Connection,
    user_id: int,
    symbols: list[str],
    bars_dir: Path,
    configs: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in symbols:
        frame = load_symbol_csv(bars_dir, symbol)
        if frame is None:
            missing.append(symbol.strip().upper())
        else:
            frames[symbol] = frame
    index_bars = load_symbol_csv(bars_dir, "VNINDEX")
    return run_frames(conn, user_id, frames, index_bars, configs), missing


def load_frames_for_run(symbols: list[str], kinds: set[str]) -> tuple[dict[str, pd.DataFrame], list[str], pd.DataFrame | None]:
    """Làm mới nến nếu file cũ hơn 4 ngày, rồi gắn dòng tiền của các filter đang bật."""
    from datetime import date, timedelta

    from config import BARS_DIR, CHART_DAYS
    from datasource.client import load_bars, load_index_bars
    from datasource.flow import load_flow, merge_net_vol

    start = (date.today() - timedelta(days=CHART_DAYS)).isoformat()
    columns = {"foreign": "foreign_net_vol", "proprietary": "prop_net_vol"}
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for symbol in symbols:
        code = symbol.strip().upper()
        try:
            bars = load_bars(code, start)
        except Exception:
            bars = load_symbol_csv(BARS_DIR, code)
        if bars is None or bars.empty:
            missing.append(code)
            continue
        for kind in sorted(kinds):
            column = columns.get(kind)
            if column is None:
                continue
            bars = merge_net_vol(bars, load_flow(code, kind), column)
        frames[code] = bars
    index_bars = load_index_bars()
    return frames, missing, index_bars
