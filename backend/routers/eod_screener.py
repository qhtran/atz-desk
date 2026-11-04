"""EOD quant screener API — ``/api/screener/eod`` (không đụng live ``POST /api/screener``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.eod_screener import FILTER_CATALOG, run_eod_screener

router = APIRouter(prefix="/api/screener", tags=["eod-screener"])


class EodScreenerBody(BaseModel):
    mode: str = Field(default="and", description="and | or")
    rsi_lt: float | None = Field(default=None, ge=0, le=100, description="RSI < threshold (oversold)")
    rsi_gt: float | None = Field(default=None, ge=0, le=100, description="RSI > threshold (overbought)")
    close_gt_sma: list[int] = Field(default_factory=list, description="Close > SMA(period); periods 20/50/200")
    volume_mult: float | None = Field(default=None, ge=0.5, le=50)
    volume_sma_period: int = Field(default=20, ge=2, le=200)
    breakout_high_period: int | None = Field(default=None, ge=5, le=120)
    symbols: list[str] | None = None
    min_bars: int = Field(default=30, ge=5, le=500)

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        m = str(v or "and").strip().lower()
        if m not in ("and", "or"):
            raise ValueError("mode must be and|or")
        return m

    @field_validator("close_gt_sma")
    @classmethod
    def _sma_periods(cls, v: list[int]) -> list[int]:
        out: list[int] = []
        for p in v or []:
            n = int(p)
            if n not in (20, 50, 200):
                raise ValueError("close_gt_sma periods limited to 20, 50, 200")
            if n not in out:
                out.append(n)
        return out


@router.get("/eod/filters")
def eod_screener_filters() -> dict[str, Any]:
    return {"ok": True, "filters": FILTER_CATALOG}


@router.post("/eod")
def eod_screener_run(body: EodScreenerBody) -> dict[str, Any]:
    if (
        body.rsi_lt is None
        and body.rsi_gt is None
        and not body.close_gt_sma
        and body.volume_mult is None
        and body.breakout_high_period is None
    ):
        raise HTTPException(status_code=400, detail="at least one filter required")
    result = run_eod_screener(
        mode=body.mode,
        rsi_lt=body.rsi_lt,
        rsi_gt=body.rsi_gt,
        close_gt_sma=body.close_gt_sma,
        volume_mult=body.volume_mult,
        volume_sma_period=body.volume_sma_period,
        breakout_high_period=body.breakout_high_period,
        symbols=body.symbols,
        min_bars=body.min_bars,
    )
    return result
