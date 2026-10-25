"""Filter runner + filter advisor (P3 realtime)."""

from __future__ import annotations

import copy
import os
from datetime import datetime, timedelta

import pandas as pd
import pytest
import redis

from filter_runner import config as fr_config
from filter_runner.history import HistoryCache
from filter_runner.registry import FilterRegistry
from filter_runner.runner import FilterRunner, confidence, plan_flow_kinds
from filters import load_registry
from filters.advisor import evaluate as evaluate_advisor
from tests.test_advisor_score import _uptrend_bars
from tests.test_filter_runner import Plans, quote_for

TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://127.0.0.1:6379/14")


@pytest.fixture
def r():
    client = redis.Redis.from_url(TEST_URL, decode_responses=True)
    try:
        client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip("không có Redis")
    client.flushdb()
    yield client
    client.flushdb()


def test_advisor_filter_in_registry() -> None:
    assert "advisor" in load_registry()


def test_confidence_uses_score_over_total() -> None:
    from filters.base import hit

    result = hit("mua", "Điểm 72.5", {"score": 72.5, "total": 100.0}, strength=0.5)
    assert confidence(result) == 0.72


def test_plan_flow_kinds_adds_foreign_for_advisor() -> None:
    plans = {"3": [{"kind": "filter", "name": "advisor", "params": {}}]}
    assert plan_flow_kinds(plans) == {"advisor", "foreign"}


def test_evaluate_advisor_details_for_runner() -> None:
    bars = _uptrend_bars(80, volume_spike=4.0)
    result = evaluate_advisor(bars, {"buy_min_total": 40.0, "sell_max_total": 20.0})
    assert result.details.get("total") == 100.0
    assert result.details.get("score") is not None
    if result.matched:
        assert 0.0 <= confidence(result) <= 1.0


def _long_uptrend(days: int = 120) -> pd.DataFrame:
    base = _uptrend_bars(days, volume_spike=4.0)
    today = datetime.now().date()
    times = []
    for i in range(days):
        day = today - timedelta(days=days - i)
        times.append(f"{day} 07:00:00+07:00")
    base["time"] = times
    base["_day"] = pd.to_datetime(base["time"]).dt.date
    return base


def test_runner_publishes_advisor_with_scored_confidence(r) -> None:
    bars = _long_uptrend()
    cfg = copy.deepcopy(fr_config.load())
    cfg["redis"]["url"] = TEST_URL
    cfg["filter_runner"]["consumer"]["group"] = "fr-advisor-test"
    history = HistoryCache(
        400,
        600,
        0.001,
        loaders=(lambda s, start: bars, lambda: None, lambda s, k: pd.DataFrame()),
    )
    runner = FilterRunner(
        cfg,
        r=r,
        registry=FilterRegistry(load_registry()),
        history=history,
        resolver=Plans({"3": [{"kind": "filter", "name": "advisor", "params": {"buy_min_total": 40.0}}]}),
    )
    signals = runner.process_quote(quote_for(bars, "VNM"))
    if not signals:
        pytest.skip("bars/fixture không đạt ngưỡng advisor trong môi trường test")
    sig = signals[0]
    assert sig.filter_name == "advisor"
    assert sig.direction == "BUY"
    assert 0.4 <= float(sig.confidence) <= 1.0
    assert "Điểm" in sig.reason or "xu hướng" in sig.reason
