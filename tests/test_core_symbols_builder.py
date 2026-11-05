"""Core Top 240 allocation builder (HOSE 120 / HNX 60 / UPCOM 60)."""

from __future__ import annotations

from pathlib import Path

from backend.board_universe import VN30_SYMBOLS
from backend.core_symbols_builder import (
    flatten_core,
    score_ohlcv_liquidity,
    select_core_symbols,
)


def test_select_core_symbols_allocation_and_vn30(tmp_path: Path):
    listing = {}
    scores = {}
    # Synthetic universe
    for i in range(200):
        listing[f"H{i:03d}"] = "HOSE"
        scores[f"H{i:03d}"] = float(200 - i)
    for i in range(100):
        listing[f"N{i:03d}"] = "HNX"
        scores[f"N{i:03d}"] = float(100 - i)
    for i in range(100):
        listing[f"U{i:03d}"] = "UPCOM"
        scores[f"U{i:03d}"] = float(100 - i)
    # Inject VN30 as HOSE with low raw score — must still be forced in
    for sym in VN30_SYMBOLS:
        listing[sym] = "HOSE"
        scores[sym] = 0.1

    picked = select_core_symbols(
        listing=listing,
        scores=scores,
        allocation={"HOSE": 120, "HNX": 60, "UPCOM": 60},
        force_vn30=True,
    )
    assert len(picked["HOSE"]) == 120
    assert len(picked["HNX"]) == 60
    assert len(picked["UPCOM"]) == 60
    for sym in VN30_SYMBOLS:
        assert sym in picked["HOSE"]
    flat = flatten_core(picked)
    assert len(flat) == 240
    assert len(set(flat)) == 240


def test_score_ohlcv_liquidity_reads_csv(tmp_path: Path):
    p = tmp_path / "ABC.csv"
    p.write_text(
        "time,open,high,low,close,volume\n"
        "2026-01-01,1,1,1,10,100\n"
        "2026-01-02,1,1,1,20,200\n",
        encoding="utf-8",
    )
    scores = score_ohlcv_liquidity(tmp_path, lookback=20)
    assert scores["ABC"] == (10 * 100 + 20 * 200) / 2
