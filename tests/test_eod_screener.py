"""Milestone 3 Phase 3–4: EOD screener filters + API."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.eod_screener import apply_eod_filters, build_symbol_snapshot, run_eod_screener
from backend.eod_store import init_eod_store, upsert_eod_bars
from backend.main import app


def _series(sym: str, start: date, n: int, close0: float, *, vol: float = 1000.0, trend: float = 0.0) -> list[dict]:
    rows = []
    px = close0
    for i in range(n):
        day = start + timedelta(days=i)
        # skip weekends roughly
        if day.weekday() >= 5:
            continue
        px = px + trend
        rows.append(
            {
                "symbol": sym,
                "trade_date": day.isoformat(),
                "open": px - 0.5,
                "high": px + 1.0,
                "low": px - 1.0,
                "close": px,
                "volume": vol,
            }
        )
    return rows


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "eod.db"
    init_eod_store(path)
    start = date(2025, 1, 2)
    # AAA: rising → high RSI, above SMAs, breakout-ish
    rows = _series("AAA", start, 280, 10.0, vol=1000, trend=0.15)
    # last bar volume spike
    rows[-1]["volume"] = 10_000
    # BBB: falling → low RSI
    rows += _series("BBB", start, 280, 50.0, vol=1000, trend=-0.12)
    upsert_eod_bars(rows, db_path=path)
    return path


def test_snapshot_and_rsi_filters(db: Path):
    result = run_eod_screener(rsi_lt=35, mode="and", db_path=db, min_bars=40)
    assert result["ok"] is True
    assert result["scanned"] >= 2
    assert result["elapsed_ms"] < 1000
    syms = {r["symbol"] for r in result["rows"]}
    assert "BBB" in syms
    assert "AAA" not in syms

    hi = run_eod_screener(rsi_gt=65, mode="and", db_path=db, min_bars=40)
    syms_hi = {r["symbol"] for r in hi["rows"]}
    assert "AAA" in syms_hi


def test_close_gt_sma_and_volume_spike(db: Path):
    up = run_eod_screener(close_gt_sma=[50], mode="and", db_path=db, min_bars=40)
    assert "AAA" in {r["symbol"] for r in up["rows"]}

    spike = run_eod_screener(volume_mult=2.5, volume_sma_period=20, mode="and", db_path=db, min_bars=40)
    assert "AAA" in {r["symbol"] for r in spike["rows"]}


def test_breakout_high(tmp_path: Path):
    path = tmp_path / "breakout.db"
    init_eod_store(path)
    start = date(2025, 6, 2)
    rows = []
    px = 20.0
    for i in range(40):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        rows.append(
            {
                "symbol": "BRK",
                "trade_date": day.isoformat(),
                "open": px,
                "high": px,  # flat highs
                "low": px - 0.5,
                "close": px,
                "volume": 1000,
            }
        )
    # last bar breaks out above prior flat highs
    rows[-1]["close"] = 25.0
    rows[-1]["high"] = 25.0
    upsert_eod_bars(rows, db_path=path)
    out = run_eod_screener(breakout_high_period=20, mode="and", db_path=path, min_bars=20)
    assert out["matched"] >= 1
    assert "BRK" in {r["symbol"] for r in out["rows"]}


def test_apply_filters_or_mode(db: Path):
    from backend.eod_store import load_eod_universe

    rows = load_eod_universe(db_path=db)
    snap = build_symbol_snapshot(rows, min_bars=40)
    both = apply_eod_filters(snap, mode="or", rsi_lt=35, rsi_gt=65)
    assert set(both["symbol"]) >= {"AAA", "BBB"}


def test_api_eod_screener(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_eod.db"
    init_eod_store(path)
    start = date(2025, 1, 2)
    upsert_eod_bars(_series("XYZ", start, 120, 20.0, trend=-0.2), db_path=path)
    import backend.eod_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)

    client = TestClient(app)
    meta = client.get("/api/screener/eod/filters")
    assert meta.status_code == 200 and meta.json()["ok"] is True

    bad = client.post("/api/screener/eod", json={"mode": "and"})
    assert bad.status_code == 400

    res = client.post("/api/screener/eod", json={"mode": "and", "rsi_lt": 40})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "eod_prices"
    assert "elapsed_ms" in body
    assert body["matched"] >= 1
