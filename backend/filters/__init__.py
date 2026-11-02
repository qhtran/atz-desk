"""Native batch filters for daily signal scan (vectorized core)."""

from backend.filters.bollinger_batch import evaluate_bollinger_batch
from backend.filters.rsi_batch import evaluate_rsi_batch

NATIVE_BATCH_FILTERS = frozenset({"rsi", "bollinger"})

BATCH_EVALUATORS = {
    "rsi": evaluate_rsi_batch,
    "bollinger": evaluate_bollinger_batch,
}

__all__ = [
    "NATIVE_BATCH_FILTERS",
    "BATCH_EVALUATORS",
    "evaluate_bollinger_batch",
    "evaluate_rsi_batch",
]
