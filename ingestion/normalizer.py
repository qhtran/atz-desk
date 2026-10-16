"""Hợp đồng Normalized Quote (tài liệu mục 2) + chuẩn hoá từ price_board của vnstock."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from ingestion.log import ERR_NORMALIZE, log


@dataclass
class Quote:
    symbol: str
    exchange: str
    timestamp: str          # ISO, +07:00
    price: float
    change: float
    change_pct: float
    volume: int | None
    open: float | None
    high: float | None
    low: float | None
    ref_price: float | None
    source: str             # "kbs" | "vci"
    batch_id: str
    latency_ms: int
    stale: bool = False     # trường bổ sung (deviation): True khi phục vụ từ cache ở chế độ degrade

    def to_dict(self) -> dict:
        return asdict(self)


VOLUME_COLUMNS = ("total_volume", "volume", "accumulated_volume", "match_volume_total", "total_vol")


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def normalize_row(row: dict, source: str, batch_id: str, latency_ms: int, now: datetime) -> Quote | None:
    symbol = str(row.get("symbol") or "").strip().upper()
    price = _num(row.get("close_price")) or _num(row.get("match_price"))
    if not symbol or not price:
        return None
    ref = _num(row.get("reference_price"))
    change = round(price - ref, 4) if ref else 0.0
    change_pct = round(change / ref * 100, 2) if ref else 0.0
    volume = next((_num(row[c]) for c in VOLUME_COLUMNS if c in row and _num(row[c]) is not None), None)
    return Quote(
        symbol=symbol,
        exchange=str(row.get("exchange") or ""),
        timestamp=now.isoformat(timespec="seconds"),
        price=price,
        change=change,
        change_pct=change_pct,
        volume=int(volume) if volume is not None else None,
        open=_num(row.get("open_price")),
        high=_num(row.get("high_price")),
        low=_num(row.get("low_price")),
        ref_price=ref,
        source=source.lower(),
        batch_id=batch_id,
        latency_ms=int(latency_ms),
    )


def normalize_frame(frame, source: str, batch_id: str, latency_ms: int, now: datetime) -> list[Quote]:
    rows = frame.to_dict("records") if hasattr(frame, "to_dict") else list(frame)
    quotes = []
    for row in rows:
        try:
            quote = normalize_row(row, source, batch_id, latency_ms, now)
        except Exception as error:  # noqa: BLE001
            quote, why = None, f"{type(error).__name__}: {error}"
        else:
            why = "missing symbol or price"
        if quote:
            quotes.append(quote)
        else:
            log("NORMALIZE", f"normalize failed: {why}", error_code=ERR_NORMALIZE,
                symbol=str(row.get("symbol") or "") or None, batch_id=batch_id, source=source.lower())
    return quotes
