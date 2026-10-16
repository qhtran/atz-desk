"""Cảnh báo đọc cache có sẵn. Không gọi mạng và không chạy nền."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd

from config import ALERTS_PATH, BULLETIN_PATH
from datasource.cache import read_cache, read_universe
from datasource.portfolio import last_close

ALERT_COLUMNS = ["id", "Mã", "Loại", "Ngưỡng", "Bật"]
ALERT_KINDS = ("Giá ≥", "Giá ≤", "Vào Top 20", "Rời Top 20", "ROE ≥")
PRICE_KINDS = {"Giá ≥", "Giá ≤", "ROE ≥"}


def list_alerts() -> pd.DataFrame:
    if not ALERTS_PATH.exists():
        return pd.DataFrame(columns=ALERT_COLUMNS)
    frame = pd.read_csv(ALERTS_PATH)
    for column in ALERT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["Ngưỡng"] = pd.to_numeric(frame["Ngưỡng"], errors="coerce")
    frame["Bật"] = pd.to_numeric(frame["Bật"], errors="coerce").fillna(0).astype(int)
    return frame[ALERT_COLUMNS]


def _write(frame: pd.DataFrame) -> None:
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(ALERTS_PATH, index=False)


def add_alert(symbol: str, kind: str, level: float | None) -> str:
    code = symbol.strip().upper()
    if not code:
        raise ValueError("thiếu mã")
    if kind not in ALERT_KINDS:
        raise ValueError("loại cảnh báo không hỗ trợ")
    if kind in PRICE_KINDS and (level is None or level <= 0):
        raise ValueError("ngưỡng phải lớn hơn 0")
    frame = list_alerts()
    item_id = uuid4().hex[:8]
    row = {"id": item_id, "Mã": code, "Loại": kind, "Ngưỡng": level, "Bật": 1}
    _write(pd.concat([frame, pd.DataFrame([row])], ignore_index=True))
    return item_id


def delete_alert(item_id: str) -> None:
    frame = list_alerts()
    _write(frame.loc[frame["id"].astype(str) != item_id])


def _top_symbols() -> set[str] | None:
    try:
        board = read_cache()
    except Exception:
        return None
    if board.empty or "Mã" not in board.columns:
        return None
    return set(board["Mã"].astype(str).str.upper())


def _roe_pct(symbol: str) -> float | None:
    universe = read_universe()
    frames = [frame for frame in (universe, _safe_cache()) if frame is not None and not frame.empty]
    for frame in frames:
        matched = frame.loc[frame["Mã"].astype(str).str.upper() == symbol, "ROE (%)"]
        if matched.empty:
            continue
        value = pd.to_numeric(matched, errors="coerce").iloc[-1]
        if pd.notna(value):
            return float(value)
    return None


def _safe_cache() -> pd.DataFrame | None:
    try:
        return read_cache()
    except Exception:
        return None


def evaluate(row: pd.Series) -> tuple[bool, str]:
    """Một cảnh báo đang bật. Trả (đã chạm, câu giải thích)."""
    symbol = str(row["Mã"]).upper()
    kind = str(row["Loại"])
    level = row["Ngưỡng"]
    if kind in {"Giá ≥", "Giá ≤"}:
        price = last_close(symbol)
        if price is None:
            return False, "Chưa có giá đóng cửa đã lưu."
        if pd.isna(level):
            return False, "Thiếu ngưỡng."
        hit = price >= float(level) if kind == "Giá ≥" else price <= float(level)
        return hit, f"Giá đóng cửa {price:.2f}, ngưỡng {float(level):.2f}."
    if kind in {"Vào Top 20", "Rời Top 20"}:
        names = _top_symbols()
        if names is None:
            return False, "Chưa có Top 20 đã lưu."
        inside = symbol in names
        if kind == "Vào Top 20":
            return inside, "Đang có trong Top 20 đã lưu." if inside else "Chưa có trong Top 20 đã lưu."
        return (not inside), "Không còn trong Top 20 đã lưu." if not inside else "Vẫn nằm trong Top 20 đã lưu."
    if kind == "ROE ≥":
        roe = _roe_pct(symbol)
        if roe is None:
            return False, "Chưa có ROE từ lần quét gần nhất."
        if pd.isna(level):
            return False, "Thiếu ngưỡng."
        hit = roe >= float(level)
        return hit, f"ROE {roe:.1f}%, ngưỡng {float(level):.1f}%."
    return False, "Loại cảnh báo không hỗ trợ."


def check_alerts() -> pd.DataFrame:
    frame = list_alerts()
    rows = []
    for _, row in frame.iterrows():
        if int(row["Bật"]) != 1:
            status, detail = False, "Đang tắt."
        else:
            status, detail = evaluate(row)
        rows.append(
            {
                "Mã": row["Mã"],
                "Loại": row["Loại"],
                "Ngưỡng": row["Ngưỡng"],
                "Trạng thái": "Đã chạm" if status else "Chưa chạm",
                "Chi tiết": detail,
            }
        )
    return pd.DataFrame(rows)


def read_bulletin() -> str | None:
    if not BULLETIN_PATH.exists():
        return None
    text = BULLETIN_PATH.read_text(encoding="utf-8").strip()
    return text or None
