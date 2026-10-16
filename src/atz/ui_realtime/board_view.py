"""Logic thuần cho bảng giá Realtime: lọc mã + cache spark URI (giảm giật fragment)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def filter_by_symbol(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    """Lọc cột Mã chứa query (không phân biệt hoa thường). Trống = giữ nguyên."""
    text = str(query or "").strip().upper()
    if not text or frame.empty or "Mã" not in frame.columns:
        return frame
    mask = frame["Mã"].astype(str).str.upper().str.contains(text, regex=False, na=False)
    return frame.loc[mask].reset_index(drop=True)


def spark_cache_key(
    code: str,
    state: str | None,
    price: float | None,
    spark: list[float] | None,
) -> tuple:
    series = spark or []
    tip = (round(float(series[-1]), 4) if series else None, len(series))
    px = round(float(price), 0) if price is not None else None
    return (str(code).upper(), state or "", px, tip)


def cached_spark_uri(
    cache: dict[str, tuple[tuple, str]],
    *,
    code: str,
    spark: list[float] | None,
    change: float | None,
    state: str | None,
    price: float | None,
    builder,
    max_entries: int = 400,
) -> str:
    """Trả URI từ cache nếu fingerprint không đổi; builder() khi miss."""
    key = spark_cache_key(code, state, price, spark)
    hit = cache.get(code)
    if hit and hit[0] == key:
        return hit[1]
    uri = builder()
    cache[code] = (key, uri)
    if len(cache) > max_entries:
        # bỏ ~1/4 mục cũ nhất theo thứ tự dict
        for drop in list(cache.keys())[: max_entries // 4]:
            cache.pop(drop, None)
    return uri


def pick_quote_row(rows: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    code = str(symbol or "").strip().upper()
    if not code:
        return None
    for row in rows:
        if str(row.get("Mã") or "").upper() == code:
            return row
    return None
