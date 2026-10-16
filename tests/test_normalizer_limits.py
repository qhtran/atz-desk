"""Normalize ceiling/floor từ price_board."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from ingestion.normalizer import normalize_row

HN = timezone(timedelta(hours=7))


def test_normalize_keeps_ceiling_floor():
    row = {
        "symbol": "FPT",
        "exchange": "HOSE",
        "reference_price": 58000.0,
        "ceiling_price": 62000.0,
        "floor_price": 54000.0,
        "close_price": 58200.0,
        "open_price": 58700.0,
        "high_price": 58700.0,
        "low_price": 57900.0,
    }
    q = normalize_row(row, "kbs", "b_test", 12, datetime.now(HN))
    assert q is not None
    assert q.ceiling_price == 62000.0 and q.floor_price == 54000.0
    assert q.ref_price == 58000.0
