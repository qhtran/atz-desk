"""Sổ vốn sidebar (F1 mục 2). CSV một dòng: nạp lần đầu / bổ sung / rút."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import CAPITAL_LEDGER_PATH, DEFAULT_CAPITAL

COLUMNS = ("initial", "additional", "withdrawn")


@dataclass(frozen=True)
class CapitalLedger:
    initial: float
    additional: float
    withdrawn: float

    @property
    def total(self) -> float:
        return max(0.0, float(self.initial) + float(self.additional) - float(self.withdrawn))


def default_ledger() -> CapitalLedger:
    return CapitalLedger(initial=float(DEFAULT_CAPITAL), additional=0.0, withdrawn=0.0)


def load_ledger(path=None) -> CapitalLedger:
    target = path if path is not None else CAPITAL_LEDGER_PATH
    if not target.exists():
        return default_ledger()
    try:
        frame = pd.read_csv(target)
    except Exception:
        return default_ledger()
    if frame.empty:
        return default_ledger()
    row = frame.iloc[0]
    values = {}
    for column in COLUMNS:
        raw = row[column] if column in frame.columns else 0.0
        try:
            number = float(raw)
        except (TypeError, ValueError):
            number = 0.0
        if pd.isna(number) or number < 0:
            number = 0.0
        values[column] = number
    if values["initial"] <= 0 and values["additional"] <= 0:
        return default_ledger()
    return CapitalLedger(**values)


def save_ledger(ledger: CapitalLedger, path=None) -> None:
    target = path if path is not None else CAPITAL_LEDGER_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {
                "initial": float(ledger.initial),
                "additional": float(ledger.additional),
                "withdrawn": float(ledger.withdrawn),
            }
        ]
    )
    frame.to_csv(target, index=False)


def nav_breakdown(
    ledger: CapitalLedger,
    securities_cost: float,
    securities_mkt: float,
) -> dict[str, float]:
    """Tiền mặt = tổng vốn − giá vốn CK; NAV = tiền mặt + GTCK thị trường."""
    cost = max(0.0, float(securities_cost))
    mkt = max(0.0, float(securities_mkt))
    total = ledger.total
    cash = max(0.0, total - cost)
    return {
        "total_capital": total,
        "securities_cost": cost,
        "securities_mkt": mkt,
        "cash": cash,
        "nav": cash + mkt,
        "pnl": mkt - cost,
    }
