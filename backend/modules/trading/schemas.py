"""Pydantic schemas for /api/trading."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TrancheRow(BaseModel):
    t: int
    qty: float
    price: float
    fee: float


class PositionView(BaseModel):
    id: int
    symbol: str
    qty: float
    avg: float
    last: float | None = None
    invested: float
    mv: float
    pnl: float
    pnlPct: float
    sl: float | None = None
    tp: list[float] = Field(default_factory=list)
    alert: Literal["idle", "sl", "tp"] = "idle"
    status: str
    tranches: list[TrancheRow] = Field(default_factory=list)


class BuyRequest(BaseModel):
    symbol: str
    tranche: int = Field(ge=1, le=5)
    qty: float = Field(gt=0)
    price: float = Field(gt=0)
    note: str = ""


class SellRequest(BaseModel):
    symbol: str
    qty: float = Field(gt=0)
    price: float = Field(gt=0)
    note: str = ""


class LevelsPatch(BaseModel):
    sl: float | None = None
    tp: list[float] | None = None


class TransactionView(BaseModel):
    id: int
    side: str
    tranche: int | None
    qty: float
    price: float
    fee: float
    tax: float
    executed_at: datetime
    note: str


class PositionDetail(PositionView):
    transactions: list[TransactionView] = Field(default_factory=list)
