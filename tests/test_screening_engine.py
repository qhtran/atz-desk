"""Milestone 4 — thin screening facade over Option B evaluator."""

from __future__ import annotations

import numpy as np

from backend.screening.engine import (
    TickRingStore,
    evaluate_rings,
    evaluate_with_control_plane,
    load_screening_config,
)


def test_load_screening_config_has_rsi_ma_volume():
    cfg = load_screening_config()
    assert isinstance(cfg, dict)
    assert "rsi" in cfg
    assert "ma" in cfg
    assert "volume_spike" in cfg


def test_evaluate_with_control_plane_delegates():
    store = TickRingStore(ring_size=80)
    for p in np.linspace(50, 20, 60):
        store.update("FPT", float(p), volume=800_000)
    store.update("FPT", 18.5, volume=4_000_000)

    cfg = load_screening_config()
    cfg = dict(cfg)
    cfg["rsi"] = {"length": 14, "oversold": 35, "overbought": 70}

    via_facade = evaluate_with_control_plane(store, cfg)
    via_direct = evaluate_rings(store, cfg)
    assert [a.to_dict() for a in via_facade] == [a.to_dict() for a in via_direct]
    assert any(a.indicator == "RSI_OVERSOLD" for a in via_facade)
