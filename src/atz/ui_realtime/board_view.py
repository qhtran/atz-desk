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


def normalize_pins(symbols: list | None, *, max_pins: int = 40) -> list[str]:
    """Chuẩn hóa danh sách ghim: upper, unique, giữ thứ tự, cắt max_pins."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in symbols or []:
        code = str(raw or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
        if len(out) >= max_pins:
            break
    return out


def sort_pinned_first(frame: pd.DataFrame, pinned: list[str] | None) -> pd.DataFrame:
    """Đưa mã ghim lên đầu (theo thứ tự pin); phần còn lại giữ nguyên thứ tự."""
    pins = normalize_pins(pinned)
    if not pins or frame.empty or "Mã" not in frame.columns:
        return frame
    order = {code: index for index, code in enumerate(pins)}
    codes = frame["Mã"].astype(str).str.upper()
    pinned_mask = codes.isin(order)
    top = frame.loc[pinned_mask].copy()
    top["_pin_ord"] = codes.loc[pinned_mask].map(order)
    top = top.sort_values("_pin_ord", kind="stable").drop(columns=["_pin_ord"])
    rest = frame.loc[~pinned_mask]
    return pd.concat([top, rest], ignore_index=True)


def detect_price_flashes(
    prev_prices: dict[str, float],
    next_prices: dict[str, float],
    *,
    min_tick: float = 50.0,
) -> dict[str, bool]:
    """So giá cũ/mới → {Mã: True=tăng / False=giảm}. Bỏ qua đổi < min_tick (VND)."""
    out: dict[str, bool] = {}
    threshold = max(0.0, float(min_tick))
    for code, price in next_prices.items():
        old = prev_prices.get(code)
        if old is None:
            continue
        delta = float(price) - float(old)
        if abs(delta) < threshold:
            continue
        out[str(code)] = delta > 0
    return out


def merge_flash_hold(
    fresh: dict[str, bool],
    hold: dict[str, dict] | None,
    *,
    hold_cycles: int = 2,
) -> tuple[dict[str, bool], dict[str, dict]]:
    """Giữ flash thêm vài chu kỳ fragment để mắt kịp thấy (SSI-like linger).

    hold[code] = {"up": bool, "left": int}
    """
    cycles = max(1, int(hold_cycles))
    state: dict[str, dict] = dict(hold or {})
    for code, up in fresh.items():
        state[code] = {"up": bool(up), "left": cycles}
    visible: dict[str, bool] = {}
    next_hold: dict[str, dict] = {}
    for code, meta in state.items():
        left = int(meta.get("left") or 0)
        if left <= 0:
            continue
        visible[code] = bool(meta.get("up"))
        remain = left - 1
        if remain > 0:
            next_hold[code] = {"up": bool(meta.get("up")), "left": remain}
    return visible, next_hold


def mark_pinned_column(frame: pd.DataFrame, pinned: list[str] | None) -> pd.DataFrame:
    """Thêm cột Ghim (★ / trống) ngay sau Mã nếu có."""
    pins = set(normalize_pins(pinned))
    if frame.empty or "Mã" not in frame.columns:
        return frame
    out = frame.copy()
    out["Ghim"] = out["Mã"].astype(str).str.upper().map(lambda c: "★" if c in pins else "")
    cols = list(out.columns)
    cols.remove("Ghim")
    if "Mã" in cols:
        i = cols.index("Mã") + 1
        ordered = cols[:i] + ["Ghim"] + cols[i:]
    else:
        ordered = ["Ghim"] + cols
    return out[ordered]


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
