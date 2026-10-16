"""Vị thế và nhật ký lưu CSV trong data/. Không gọi mạng."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pandas as pd

from config import BARS_DIR, CAPITAL_TRANCHES, HN_ZONE, JOURNAL_PATH, POSITIONS_PATH, THOUSAND_VND

POSITION_COLUMNS = ["id", "Mã", "Giá mua", "Khối lượng", "Ngày mua", "Phần đã giải ngân"]
JOURNAL_COLUMNS = ["id", "Thời điểm", "Mã", "Chiều", "Ghi chú"]


def _read(path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[columns]


def _write(path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def list_positions() -> pd.DataFrame:
    frame = _read(POSITIONS_PATH, POSITION_COLUMNS)
    if frame.empty:
        return frame
    frame["Giá mua"] = pd.to_numeric(frame["Giá mua"], errors="coerce")
    frame["Khối lượng"] = pd.to_numeric(frame["Khối lượng"], errors="coerce")
    frame["Phần đã giải ngân"] = pd.to_numeric(frame["Phần đã giải ngân"], errors="coerce")
    return frame


def add_position(symbol: str, buy_price: float, shares: float, buy_date: str, tranches: int) -> str:
    code = symbol.strip().upper()
    if not code:
        raise ValueError("thiếu mã")
    if buy_price <= 0 or shares <= 0:
        raise ValueError("giá mua và khối lượng phải lớn hơn 0")
    if tranches < 1 or tranches > CAPITAL_TRANCHES:
        raise ValueError(f"số phần phải từ 1 đến {CAPITAL_TRANCHES}")
    frame = list_positions()
    item_id = uuid4().hex[:8]
    row = {
        "id": item_id,
        "Mã": code,
        "Giá mua": buy_price,
        "Khối lượng": shares,
        "Ngày mua": buy_date,
        "Phần đã giải ngân": int(tranches),
    }
    _write(POSITIONS_PATH, pd.concat([frame, pd.DataFrame([row])], ignore_index=True))
    return item_id


def delete_position(item_id: str) -> None:
    frame = list_positions()
    kept = frame.loc[frame["id"].astype(str) != item_id]
    _write(POSITIONS_PATH, kept)


def last_close(symbol: str) -> float | None:
    """Giá đóng cửa cuối trong data/ohlcv. Không có file thì trả None."""
    path = BARS_DIR / f"{symbol}.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if "close" not in frame.columns or frame.empty:
        return None
    closes = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])


def profit_vnd(buy_price: float, shares: float, last_price: float | None) -> float | None:
    if last_price is None or pd.isna(buy_price) or pd.isna(shares):
        return None
    return (float(last_price) - float(buy_price)) * float(shares) * THOUSAND_VND


def tranche_usage(frame: pd.DataFrame) -> pd.DataFrame:
    """Tổng số phần đã ghi cho từng mã, so với CAPITAL_TRANCHES."""
    if frame.empty:
        return pd.DataFrame(columns=["Mã", "Phần đã giải ngân", "Phần còn lại"])
    grouped = frame.groupby("Mã", as_index=False)["Phần đã giải ngân"].sum()
    grouped["Phần còn lại"] = CAPITAL_TRANCHES - grouped["Phần đã giải ngân"]
    return grouped


def list_journal() -> pd.DataFrame:
    frame = _read(JOURNAL_PATH, JOURNAL_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values("Thời điểm", ascending=False).reset_index(drop=True)


def add_journal(symbol: str, side: str, note: str) -> str:
    code = symbol.strip().upper()
    text = note.strip()
    if not code:
        raise ValueError("thiếu mã")
    if side not in {"Mua", "Bán"}:
        raise ValueError("chiều phải là Mua hoặc Bán")
    if not text:
        raise ValueError("thiếu ghi chú")
    frame = list_journal()
    item_id = uuid4().hex[:8]
    moment = datetime.now(HN_ZONE).strftime("%Y-%m-%d %H:%M")
    row = {"id": item_id, "Thời điểm": moment, "Mã": code, "Chiều": side, "Ghi chú": text}
    _write(JOURNAL_PATH, pd.concat([frame, pd.DataFrame([row])], ignore_index=True))
    return item_id


def delete_journal(item_id: str) -> None:
    frame = list_journal()
    kept = frame.loc[frame["id"].astype(str) != item_id]
    _write(JOURNAL_PATH, kept)
