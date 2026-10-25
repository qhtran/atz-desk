"""Filter cố vấn — chấm điểm 0–100, khớp khi vượt ngưỡng mua."""

from __future__ import annotations

import pandas as pd

from engine.advisor_score import compute_advisor_score, load_advisor_config
from filters.base import FilterSpec, ParamSpec, SignalResult, hit, hold, resolve_params, waiting

_CFG = load_advisor_config()
_TH = _CFG["thresholds"]
_ST = _CFG["short_term"]
_FLOW = _CFG["flow"]

FILTER = FilterSpec(
    name="advisor",
    label="Cố vấn (0–100)",
    description="Tổng hợp xu hướng, dòng tiền và KT ngắn hạn thành điểm 0–100.",
    group="cố vấn",
    params=(
        ParamSpec("buy_min_total", "float", float(_TH["buy_min_total"]), "Điểm tối thiểu (mua)", min=0, max=100),
        ParamSpec("sell_max_total", "float", float(_TH["sell_max_total"]), "Điểm tối đa (bán)", min=0, max=100),
        ParamSpec("foreign_days", "int", int(_FLOW["foreign_days"]), "Phiên KN ròng", min=1, max=20),
        ParamSpec("volume_spike", "float", float(_FLOW["volume_spike"]), "Hệ số KL đột biến", min=1, max=10),
        ParamSpec("rsi_low", "float", float(_ST["rsi_buy_zone"][0]), "RSI vùng mua (min)", min=1, max=50),
        ParamSpec("rsi_high", "float", float(_ST["rsi_buy_zone"][1]), "RSI vùng mua (max)", min=30, max=60),
    ),
)


def _params_for_engine(chosen: dict) -> dict:
    return {
        "thresholds": {
            "buy_min_total": chosen["buy_min_total"],
            "sell_max_total": chosen["sell_max_total"],
        },
        "flow": {
            "foreign_days": chosen["foreign_days"],
            "volume_spike": chosen["volume_spike"],
        },
        "short_term": {
            "rsi_buy_zone": [chosen["rsi_low"], chosen["rsi_high"]],
        },
    }


def evaluate(bars: pd.DataFrame, params: dict | None = None) -> SignalResult:
    chosen = resolve_params(FILTER, params)
    score = compute_advisor_score(bars, _params_for_engine(chosen))
    if score.total is None:
        return waiting(score.reason)
    details = {
        "total": 100.0,
        "pillars": score.pillars,
        "recommendation": score.recommendation,
        "flow_partial": score.flow_partial,
        "score": score.total,
        "max_score": 100.0,
    }
    strength = round(score.total / 100.0, 4)
    if score.recommendation == "mua" and score.total >= chosen["buy_min_total"]:
        return hit("mua", score.reason, details, strength=strength)
    if score.recommendation == "ban" and score.total <= chosen["sell_max_total"]:
        return hit("ban", score.reason, details, strength=strength)
    return hold(score.reason, details)
