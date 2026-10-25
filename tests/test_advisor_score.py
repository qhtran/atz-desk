"""Engine advisor_score — ba trụ 0–100."""

from __future__ import annotations

from engine.advisor_score import compute_advisor_score, min_bars_needed, resolve_advisor_params
from tests.bars import frame


def _uptrend_bars(n: int = 70, *, volume_spike: float = 3.0, foreign: bool = True) -> pd.DataFrame:
    closes = [10.0 + i * 0.15 for i in range(n)]
    volumes = [120_000.0] * (n - 1) + [120_000.0 * volume_spike]
    bars = frame(closes, volumes)
    if foreign:
        net = [0.0] * (n - 5) + [50_000.0] * 5
        bars["foreign_net_vol"] = net
    return bars


def test_bullish_setup_scores_high() -> None:
    bars = _uptrend_bars()
    cfg = resolve_advisor_params(None)
    assert len(bars) >= min_bars_needed(cfg)
    score = compute_advisor_score(bars)
    assert score.total is not None
    assert score.total >= 55.0
    assert score.pillars["trend"]["points"] >= 25.0
    assert score.recommendation in {"mua", "giu", "ban"}


def test_missing_foreign_uses_volume_only() -> None:
    bars = _uptrend_bars(foreign=False)
    score = compute_advisor_score(bars)
    assert score.total is not None
    assert score.flow_partial is True
    assert score.pillars["flow"]["breakdown"]["foreign"]["available"] is False


def test_short_bars_returns_none() -> None:
    bars = frame([1.0, 2.0, 3.0, 4.0, 5.0])
    score = compute_advisor_score(bars)
    assert score.total is None
    assert score.reason == "không đủ dữ liệu"


def test_buy_recommendation_when_threshold_met() -> None:
    bars = _uptrend_bars(volume_spike=4.0)
    score = compute_advisor_score(bars, {"thresholds": {"buy_min_total": 50, "sell_max_total": 20}})
    assert score.total is not None
    if score.total >= 50:
        assert score.recommendation == "mua"
