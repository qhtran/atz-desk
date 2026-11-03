"""Thin facade over Option B stream evaluator + control-plane params.

Does not re-implement RSI / MA / volume spike — delegates to
``backend.engine.stream_evaluator`` and loads thresholds from the Admin
control plane (YAML + JSON overlay) when available.
"""

from __future__ import annotations

from typing import Any

from backend.engine.stream_evaluator import (
    StreamAlert,
    TickRingStore,
    evaluate_rings,
)
from backend.engine.stream_listener import (
    load_effective_stream_alerts_config,
    load_stream_alerts_config,
)

__all__ = [
    "StreamAlert",
    "TickRingStore",
    "evaluate_rings",
    "evaluate_with_control_plane",
    "load_screening_config",
]


def load_screening_config() -> dict[str, Any]:
    """Effective stream-alerts config (control-plane overlay when present)."""
    return load_effective_stream_alerts_config()


def evaluate_with_control_plane(
    store: TickRingStore,
    cfg: dict[str, Any] | None = None,
) -> list[StreamAlert]:
    """Evaluate tick rings using control-plane (or YAML) parameters."""
    chosen = cfg if isinstance(cfg, dict) and cfg else load_screening_config()
    if not chosen:
        chosen = load_stream_alerts_config()
    return evaluate_rings(store, chosen)
