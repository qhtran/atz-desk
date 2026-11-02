"""Phase 3A — advisor scoring vectorized (pandas panel)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.core.trading_config import (
    load_trading_config,
    risk_meta_for_user,
    scoring_config_for_user,
)
from backend.engine.advisor_score import hits_from_panels, score_frame_from_panels


def _synth_bars(n: int = 80, *, bullish: bool = True) -> pd.DataFrame:
    rng = np.linspace(10.0, 20.0 if bullish else 8.0, n)
    noise = np.sin(np.arange(n) / 5.0) * 0.2
    close = rng + noise
    volume = np.full(n, 1_000_000.0)
    volume[-1] = 3_000_000.0  # spike
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": volume,
        }
    )


def test_score_frame_vectorized_matrix():
    panels = {
        "AAA": _synth_bars(bullish=True),
        "BBB": _synth_bars(bullish=False),
        "CCC": _synth_bars(n=5, bullish=True),  # thiếu nến
    }
    cfg = scoring_config_for_user(None)
    cfg["buy_min_total"] = 50
    frame = score_frame_from_panels(panels, cfg)
    assert list(frame.index) == ["AAA", "BBB", "CCC"]
    assert pd.isna(frame.loc["CCC", "score"])
    assert frame.loc["AAA", "score"] >= frame.loc["BBB", "score"]
    assert set(frame.columns) >= {"score", "trend", "flow", "short_term", "recommendation", "reason"}


def test_hits_include_score_and_risk_meta():
    panels = {"AAA": _synth_bars(bullish=True), "BBB": _synth_bars(bullish=True)}
    cfg = scoring_config_for_user(None)
    cfg["buy_min_total"] = 0
    meta = risk_meta_for_user(None)
    hits = hits_from_panels(panels, cfg, buy_min_total=0, risk_meta=meta)
    assert len(hits) == 2
    assert all("score" in h and "risk_meta" in h for h in hits)
    assert hits[0]["score"] >= hits[1]["score"]
    assert hits[0]["risk_meta"]["profile"] == "default"


def test_trading_station_yaml_risk_scaffolding():
    load_trading_config.cache_clear()
    cfg = load_trading_config()
    assert "position_sizing" in cfg
    assert "risk_tolerance" in cfg
    assert "scoring_thresholds" in cfg
    assert "profiles" in cfg["risk_tolerance"]
    assert "weights" in cfg["scoring_thresholds"]
    meta = risk_meta_for_user("unknown_user")
    assert meta["profile"] == "default"
    assert "position_sizing" in meta
