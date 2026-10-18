"""Tests for scripts/tools/sector_universe (branch feat/sector-universe-f3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "tools" / "sector_universe"
sys.path.insert(0, str(TOOL))

from common import (  # noqa: E402
    ThemeSpec,
    candidate_symbols,
    load_themes,
    load_universe_config,
    top_k_for_theme,
)
from features import build_feature_table  # noqa: E402
from score import select_theme, score_frame  # noqa: E402


def _write_bars(path: Path, symbol: str, vol: float, close: float, n: int = 40) -> None:
    path.mkdir(parents=True, exist_ok=True)
    rows = []
    price = close
    for i in range(n):
        rows.append(
            {
                "time": f"2026-01-{i+1:02d}" if i < 28 else f"2026-02-{i-27:02d}",
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": vol,
            }
        )
        price *= 1.001
    pd.DataFrame(rows).to_csv(path / f"{symbol}.csv", index=False)


@pytest.fixture
def mini_env(tmp_path: Path):
    themes = {
        "themes": {
            "thep": {
                "label": "Thép",
                "symbols": ["HPG", "HSG", "NKG"],
                "icb_names": ["Kim loại"],
                "whitelist": [],
            },
            "cong_nghe": {
                "label": "Công nghệ",
                "symbols": ["FPT", "CMG"],
                "icb_names": ["Phần mềm & Dịch vụ Máy tính"],
                "whitelist": [],
            },
        }
    }
    themes_path = tmp_path / "themes.yaml"
    themes_path.write_text(yaml.safe_dump(themes, allow_unicode=True), encoding="utf-8")

    industry = pd.DataFrame(
        {
            "symbol": ["HPG", "HSG", "NKG", "SMC", "FPT", "CMG", "ELC", "AAA"],
            "icb_name": [
                "Kim loại",
                "Kim loại",
                "Kim loại",
                "Kim loại",
                "Phần mềm & Dịch vụ Máy tính",
                "Phần mềm & Dịch vụ Máy tính",
                "Phần mềm & Dịch vụ Máy tính",
                "Hóa chất",
            ],
        }
    )
    industry_path = tmp_path / "industry.csv"
    industry.to_csv(industry_path, index=False)

    bars = tmp_path / "ohlcv"
    # Seed thép thanh khoản cao; SMC peer thấp hơn một chút.
    _write_bars(bars, "HPG", 5_000_000, 20)
    _write_bars(bars, "HSG", 2_000_000, 15)
    _write_bars(bars, "NKG", 1_200_000, 12)
    _write_bars(bars, "SMC", 900_000, 10)
    _write_bars(bars, "FPT", 3_000_000, 100)
    _write_bars(bars, "CMG", 800_000, 50)
    _write_bars(bars, "ELC", 400_000, 30)  # dưới 500k

    cfg_path = tmp_path / "sector_universe.yaml"
    cfg = {
        "paths": {
            "themes": str(themes_path),
            "industry": str(industry_path),
            "bars_dir": str(bars),
            "output_dir": str(tmp_path / "out"),
        },
        "features": {"volume_window": 20, "min_bars": 25, "atr_window": 14},
        "defaults": {
            "w_log_gtgd": 0.55,
            "w_log_vol": 0.35,
            "w_atr": 0.10,
            "min_vol20": 500_000,
            "k_ratio": 1.0,
            "k_min": 3,
            "k_max": 10,
            "keep_seed_if_listed": True,
            "keep_whitelist": True,
        },
        "fit_grid": {
            "w_log_gtgd": [0.55],
            "w_log_vol": [0.35],
            "w_atr": [0.10],
            "min_vol20": [500_000],
            "k_ratio": [1.0],
        },
        "fit_objective": {"recall_weight": 0.7, "precision_weight": 0.3},
        "pull": {},
        "fitted": {},
    }
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return cfg_path


def test_load_real_f3_themes():
    path = ROOT / "config" / "sector_themes_f3.yaml"
    themes = load_themes(path)
    assert len(themes) == 14
    keys = {t.key for t in themes}
    assert "chung_khoan" in keys and "thep" in keys
    # CTS không còn ở năng lượng
    energy = next(t for t in themes if t.key == "nang_luong")
    assert "CTS" not in energy.symbols


def test_top_k_clamp():
    assert top_k_for_theme(5, {"k_ratio": 1.0, "k_min": 5, "k_max": 22}) == 5
    assert top_k_for_theme(20, {"k_ratio": 1.25, "k_min": 5, "k_max": 22}) == 22


def test_candidate_excludes_other_seeds():
    a = ThemeSpec("a", "A", ["HPG"], ["Kim loại"])
    b = ThemeSpec("b", "B", ["SMC"], ["Kim loại"])
    industry = {"HPG": "Kim loại", "SMC": "Kim loại", "NKG": "Kim loại"}
    pool = candidate_symbols(a, industry, exclude={"SMC"})
    assert "HPG" in pool and "NKG" in pool and "SMC" not in pool


def test_select_recovers_seed(mini_env: Path):
    cfg = load_universe_config(mini_env)
    themes = load_themes(cfg.themes_path)
    thep = next(t for t in themes if t.key == "thep")
    industry = {"HPG": "Kim loại", "HSG": "Kim loại", "NKG": "Kim loại", "SMC": "Kim loại"}
    selected, metrics = select_theme(
        thep,
        ["HPG", "HSG", "NKG", "SMC"],
        cfg,
    )
    assert metrics["recall"] == 1.0
    assert set(thep.symbols).issubset(set(selected["symbol"]))


def test_score_ranks_higher_liquidity_first(mini_env: Path):
    cfg = load_universe_config(mini_env)
    feats = build_feature_table(["HPG", "SMC"], cfg)
    scored = score_frame(feats, cfg.params).sort_values("score", ascending=False)
    assert scored.iloc[0]["symbol"] == "HPG"


def test_fit_and_daily_smoke(mini_env: Path):
    from fit import fit_params, write_fitted
    from run_filter import run

    result = fit_params(mini_env)
    assert result["recall"] >= 0.9
    write_fitted(mini_env, result)
    out = run("daily", mini_env)
    assert (out / "summary.md").exists()
    assert (out / "universe_all.csv").exists()
