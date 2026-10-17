"""Chỉ số nóng từ Redis ``idx:quote:{symbol}`` (cùng feed Realtime index cards).

Miss / lỗi → caller giữ OHLCV. Không import Streamlit.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

log = logging.getLogger(__name__)

QUOTE_KEY = "idx:quote:{symbol}"

# Tên hiển thị Overview → mã Redis / index-feed
DISPLAY_TO_REDIS = {
    "VNIndex": "VNINDEX",
    "HNXIndex": "HNXINDEX",
    "UPIndex": "UPCOMINDEX",
    "VN30": "VN30",
    "VN30F1M": "VN30F1M",
    "VN30F2M": "VN30F2M",
}


def load_idx_quotes(
    symbols: list[str],
    *,
    client=None,
    quote_key: str = QUOTE_KEY,
    redis_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    """MGET → {SYMBOL: quote dict}. Rỗng nếu không kết nối."""
    syms = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not syms:
        return {}
    try:
        if client is None:
            if not redis_url:
                from ui_realtime import config as ui_config

                cfg = ui_config.load()
                redis_url = cfg["redis"]["url"]
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        keys = [quote_key.format(symbol=s) for s in syms]
        raws = client.mget(keys)
    except (redis.exceptions.RedisError, OSError, KeyError, TypeError) as exc:
        log.debug("idx_quotes miss: %s", exc)
        return {}

    out: dict[str, dict[str, Any]] = {}
    for sym, raw in zip(syms, raws or []):
        if not raw:
            continue
        try:
            data = json.loads(raw)
            value = float(data["value"])
            ref = float(data["ref"])
        except (ValueError, TypeError, KeyError):
            continue
        if ref == 0:
            continue
        change = data.get("change")
        pct = data.get("pct")
        try:
            change_f = float(change) if change is not None else value - ref
            pct_f = float(pct) if pct is not None else round((value - ref) / ref * 100, 2)
        except (TypeError, ValueError):
            change_f = value - ref
            pct_f = round((value - ref) / ref * 100, 2)
        out[sym] = {
            "symbol": sym,
            "value": value,
            "ref": ref,
            "change": change_f,
            "pct": pct_f,
            "ts": data.get("ts"),
            "data_time": data.get("data_time"),
            "source": data.get("source"),
        }
    return out


def apply_idx_quote_to_row(row: dict[str, str], quote: dict[str, Any] | None) -> bool:
    """Ghi đè Tham chiếu / Đóng cửa / Tăng/giảm / Mũi tên. True nếu áp dụng."""
    if not quote:
        return False
    try:
        value = float(quote["value"])
        ref = float(quote["ref"])
        change = float(quote["change"])
        pct = float(quote["pct"])
    except (KeyError, TypeError, ValueError):
        return False
    if ref == 0:
        return False
    from ui.session_arrow import session_arrow_or_dash

    row["Tham chiếu"] = f"{ref:,.2f}"
    row["Đóng cửa"] = f"{value:,.2f}"
    row["Tăng/giảm (điểm/%)"] = f"{change:+,.2f} / {pct:+.2f}%"
    row["Mũi tên"] = session_arrow_or_dash(ref, max(value, ref), min(value, ref), value)
    return True


def overlay_vietnam_index_board(
    board,
    quotes: dict[str, dict[str, Any]] | None = None,
    *,
    use_live: bool = True,
):
    """Overlay từng hàng Chỉ số từ idx:quote. Gắn attrs nguồn / số hit / ts mới nhất."""
    import pandas as pd

    if board is None or getattr(board, "empty", True):
        empty = board if board is not None else pd.DataFrame()
        if hasattr(empty, "attrs"):
            empty.attrs["index_price_source"] = "ohlcv"
            empty.attrs["index_redis_hits"] = 0
            empty.attrs["index_quote_ts"] = None
        return empty

    work = board.copy()
    redis_syms = [DISPLAY_TO_REDIS.get(str(name), str(name).upper()) for name in work["Chỉ số"]]
    if quotes is None and use_live:
        quotes = load_idx_quotes(redis_syms)
    if quotes is None:
        quotes = {}

    hits = 0
    latest_ts = None
    for index, row in work.iterrows():
        display = str(row.get("Chỉ số") or "")
        redis_sym = DISPLAY_TO_REDIS.get(display, display.upper())
        quote = quotes.get(redis_sym)
        as_dict = row.to_dict()
        if apply_idx_quote_to_row(as_dict, quote):
            for key, value in as_dict.items():
                work.at[index, key] = value
            hits += 1
            ts = quote.get("ts") if quote else None
            try:
                ts_f = float(ts) if ts is not None else None
            except (TypeError, ValueError):
                ts_f = None
            if ts_f is not None and (latest_ts is None or ts_f > latest_ts):
                latest_ts = ts_f

    work.attrs["index_price_source"] = "redis" if hits else "ohlcv"
    work.attrs["index_redis_hits"] = int(hits)
    work.attrs["index_quote_ts"] = latest_ts
    return work
