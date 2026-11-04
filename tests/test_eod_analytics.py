"""Milestone 3 Phase 1–2: eod_prices store, ingest stub, indicator math."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.eod_indicators import (
    compute_indicator_bundle,
    ema,
    macd,
    rsi,
    sma,
    volume_spike,
)
from backend.eod_ingest import ingest_csv, rows_from_csv, sync_from_equity_eod
from backend.eod_store import (
    count_eod_bars,
    init_eod_store,
    load_eod_frame,
    upsert_eod_bar,
    upsert_eod_bars,
)
from backend.market_db import init_market_db


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "market.db"
    init_eod_store(path)
    return path


def test_sma_exact():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert pd.isna(out.iloc[0]) and pd.isna(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[3] == pytest.approx(3.0)
    assert out.iloc[4] == pytest.approx(4.0)


def test_ema_reacts_to_latest():
    s = pd.Series([10.0, 10.0, 10.0, 10.0, 20.0])
    out = ema(s, 3)
    assert out.iloc[-1] > out.iloc[-2]
    assert out.iloc[-1] == pytest.approx(ema(s, 3).iloc[-1])


def test_rsi_all_gains_near_100():
    s = pd.Series(np.arange(1.0, 40.0, 1.0))
    out = rsi(s, 14)
    assert out.iloc[-1] == pytest.approx(100.0, abs=0.01)


def test_rsi_all_losses_near_0():
    s = pd.Series(np.arange(40.0, 1.0, -1.0))
    out = rsi(s, 14)
    assert out.iloc[-1] == pytest.approx(0.0, abs=0.01)


def test_macd_columns_and_hist():
    s = pd.Series(np.linspace(100, 120, 80))
    df = macd(s, fast=12, slow=26, signal=9)
    assert list(df.columns) == ["macd", "signal", "hist"]
    assert np.isfinite(df["macd"].iloc[-1])
    assert df["hist"].iloc[-1] == pytest.approx(df["macd"].iloc[-1] - df["signal"].iloc[-1])


def test_volume_spike_flag():
    vol = pd.Series([100.0] * 20 + [400.0])
    out = volume_spike(vol, lookback=20, mult=2.5)
    assert bool(out["spike"].iloc[-1]) is True
    assert out["ratio"].iloc[-1] == pytest.approx(4.0)
    assert bool(out["spike"].iloc[-2]) is False


def test_compute_indicator_bundle_on_rows():
    rows = [
        {
            "trade_date": f"2026-01-{d:02d}",
            "open": 10 + d,
            "high": 11 + d,
            "low": 9 + d,
            "close": 10.5 + d,
            "volume": 1000 + d * 10,
        }
        for d in range(1, 31)
    ]
    # bump last volume for spike
    rows[-1]["volume"] = 50_000
    frame = compute_indicator_bundle(rows, vol_lookback=10, vol_mult=2.5)
    assert "sma_10" in frame.columns and "rsi" in frame.columns and "macd" in frame.columns
    assert np.isfinite(frame["rsi"].iloc[-1])
    assert bool(frame["vol_spike"].iloc[-1]) is True


def test_eod_store_upsert_and_load(db: Path):
    upsert_eod_bar(
        symbol="fpt",
        trade_date="20260115",
        open_=90,
        high=95,
        low=89,
        close=94,
        volume=1_000_000,
        db_path=db,
    )
    upsert_eod_bars(
        [
            {
                "symbol": "FPT",
                "trade_date": "2026-01-16",
                "open": 94,
                "high": 96,
                "low": 93,
                "close": 95,
                "volume": 1_100_000,
            }
        ],
        db_path=db,
    )
    rows = load_eod_frame("FPT", db_path=db)
    assert len(rows) == 2
    assert rows[0]["trade_date"] == "2026-01-15"
    assert rows[1]["close"] == 95.0
    assert count_eod_bars(symbol="FPT", db_path=db) == 2


def test_ingest_csv_and_equity_eod_sync(tmp_path: Path):
    db = tmp_path / "market.db"
    csv_path = tmp_path / "FPT.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-02-01,10,11,9,10.5,1000\n"
        "2026-02-02,10.5,12,10,11.5,2000\n",
        encoding="utf-8",
    )
    parsed = rows_from_csv(csv_path, default_symbol="FPT")
    assert len(parsed) == 2
    res = ingest_csv(csv_path, default_symbol="FPT", db_path=db)
    assert res["upserted"] == 2
    assert count_eod_bars(symbol="FPT", db_path=db) == 2

    init_market_db(db)
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO equity_eod (trading_date, symbol, exchange, open, high, low, close, volume)
        VALUES ('2026-02-03', 'VNM', 'HOSE', 70, 72, 69, 71, 5000)
        """
    )
    conn.commit()
    conn.close()
    sync = sync_from_equity_eod(db_path=db)
    assert sync["upserted"] >= 1
    assert count_eod_bars(symbol="VNM", db_path=db) == 1
