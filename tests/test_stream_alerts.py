"""Option B — real-time stream evaluator + alert contract."""

from __future__ import annotations

import numpy as np

from backend.engine.stream_evaluator import TickRingStore, evaluate_rings
from backend.engine.stream_listener import load_stream_alerts_config


def test_load_stream_alerts_config():
    cfg = load_stream_alerts_config()
    assert cfg.get("enabled") is True
    assert "rsi" in cfg
    assert int(cfg["rsi"]["length"]) >= 2


def test_evaluate_rings_rsi_oversold_contract():
    store = TickRingStore(ring_size=80)
    # descending closes → RSI thấp
    prices = np.linspace(50, 20, 60)
    for p in prices:
        store.update("SSI", float(p), volume=1_000_000)
    store.update("SSI", 19.0, volume=5_000_000)  # spike

    cfg = load_stream_alerts_config()
    cfg["rsi"] = {"length": 14, "oversold": 35, "overbought": 70}
    cfg["cooldown_sec"] = 0
    alerts = evaluate_rings(store, cfg)
    assert alerts
    row = next(a for a in alerts if a.indicator == "RSI_OVERSOLD")
    payload = row.to_dict()
    assert payload["type"] == "alert"
    assert payload["symbol"] == "SSI"
    assert "timestamp" in payload
    assert payload["indicator"] == "RSI_OVERSOLD"
    assert 0 <= float(payload["score"]) <= 100
    assert payload["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert isinstance(payload["message"], str) and payload["message"]


def test_evaluate_rings_empty_store():
    store = TickRingStore()
    assert evaluate_rings(store, load_stream_alerts_config()) == []
