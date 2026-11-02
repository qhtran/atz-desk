"""Native quant engines (ATZ Desk) — không phụ thuộc Streamlit legacy path."""

from backend.engine.advisor_score import (
    AdvisorBatchResult,
    hits_from_panels,
    score_frame_from_panels,
)

__all__ = [
    "AdvisorBatchResult",
    "hits_from_panels",
    "score_frame_from_panels",
]
