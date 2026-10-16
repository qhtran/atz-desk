"""Order Action Helper: chỉ đọc signal_history của chính user (tín hiệu vị thế pos_* là riêng tư).

Không đặt lệnh, không gửi tin. Deep-link app sàn (tuỳ chọn trong thiết kế) chưa làm.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from ui_realtime.log import TZ, log

ERR_OAH_FILTER = "ERR-UI-005"   # tham số lọc lịch sử không hợp lệ
ERR_OAH_DETAILS = "ERR-UI-006"  # bản ghi signal_history hỏng details (JSON) -> hiển thị thiếu lý do

DIR = {"buy": "MUA", "mua": "MUA", "sell": "BÁN", "ban": "BÁN", "bán": "BÁN"}
SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,10}$")
MAX_DAYS, MAX_LIMIT = 365, 500
# Giá trị signal_type (thường) theo chiều; SQLite lower() không hạ chữ có dấu nên liệt kê cả "BÁN".
SIDE_SQL = {"MUA": ("mua", "buy"), "BÁN": ("ban", "bán", "BÁN", "sell")}


class FilterError(ValueError):
    def __init__(self, msg: str):
        super().__init__(msg)
        self.code = ERR_OAH_FILTER


def direction(v) -> str:
    return DIR.get(str(v or "").strip().lower(), str(v or "?").upper())


def _local(ts: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(TZ)


def format_signal(row: dict) -> dict:
    """row: bản ghi signal_history (dict). Trả dict chuẩn + text hiển thị + chuỗi copy."""
    details_raw = row.get("details") or "{}"
    try:
        details = json.loads(details_raw) if isinstance(details_raw, str) else dict(details_raw)
    except (ValueError, TypeError):
        details = {}
        log("OAH-DETAILS", "bad details json", error_code=ERR_OAH_DETAILS, symbol=row.get("symbol"),
            user_id=row.get("user_id"), history_id=row.get("id"))
    when = _local(details.get("timestamp") or row.get("detected_at"))
    price = row.get("gia_tai_thoi_diem")
    price = details.get("price", price) if price is None else price
    d = direction(row.get("signal_type"))
    sym = str(row.get("symbol") or "").upper()
    price_txt = f"{float(price):,.0f}" if price is not None else "-"
    reason = details.get("reason") or ""
    filt = str(row.get("filter_name") or "")
    ts_txt = when.strftime("%d/%m/%Y %H:%M") if when else str(row.get("detected_at") or "")
    text = f"{d} {sym} @ {price_txt} | {filt}" + (f" | {reason}" if reason else "") + f" | {ts_txt}"
    copy = f"{sym} {d} {price_txt.replace(',', '') if price is not None else ''}".strip()
    return {"id": row.get("id"), "signal_id": details.get("signal_id"), "symbol": sym, "direction": d,
            "price": None if price is None else float(price), "filter_name": filt, "reason": reason,
            "time": when, "time_text": ts_txt, "private": filt.startswith("pos_"), "text": text, "copy": copy}


def validate(days, limit, symbol: str | None, side: str | None) -> tuple[int, int, str | None, str | None]:
    try:
        days, limit = int(days), int(limit)
    except (TypeError, ValueError):
        raise FilterError("số ngày / số dòng phải là số nguyên")
    if not 1 <= days <= MAX_DAYS:
        raise FilterError(f"số ngày phải 1..{MAX_DAYS}")
    if not 1 <= limit <= MAX_LIMIT:
        raise FilterError(f"số dòng phải 1..{MAX_LIMIT}")
    symbol = (symbol or "").strip().upper() or None
    if symbol and not SYMBOL_RE.match(symbol):
        raise FilterError("mã chứng khoán không hợp lệ")
    side = (side or "").strip().upper() or None
    if side not in (None, "MUA", "BÁN"):
        raise FilterError("chiều phải MUA hoặc BÁN")
    return days, limit, symbol, side


def history(conn, user_id: int, days=7, limit=100, symbol: str | None = None, side: str | None = None,
            now: datetime | None = None) -> list[dict]:
    """Lịch sử tín hiệu CỦA user_id (luôn lọc theo user, kể cả pos_*). Mới nhất trước, gộp trùng signal_id."""
    try:
        days, limit, symbol, side = validate(days, limit, symbol, side)
    except FilterError as e:
        log("OAH-HISTORY", str(e), error_code=e.code, user_id=user_id)
        raise
    since = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).astimezone(timezone.utc).isoformat(timespec="seconds")
    sql = ("SELECT id, user_id, symbol, filter_name, signal_type, detected_at, details, gia_tai_thoi_diem "
           "FROM signal_history WHERE user_id = ? AND detected_at >= ?")
    args: list = [int(user_id), since]
    if symbol:
        sql += " AND symbol = ?"
        args.append(symbol)
    if side:
        vals = SIDE_SQL[side]
        sql += f" AND lower(trim(signal_type)) IN ({','.join('?' * len(vals))})"
        args.extend(vals)
    sql += " ORDER BY detected_at DESC, id DESC LIMIT ?"
    args.append(limit * 2)
    cur = conn.execute(sql, args)
    cols = [c[0] for c in cur.description]
    out, seen = [], set()
    for r in cur.fetchall():
        s = format_signal(dict(zip(cols, r)))
        if side and s["direction"] != side:
            continue
        k = s["signal_id"] or s["id"]
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= limit:
            break
    log("OAH-HISTORY", f"{len(out)} rows days={days} symbol={symbol} side={side}", user_id=user_id, rows=len(out))
    return out


def to_csv(items: list[dict]) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["thoi_gian", "ma", "chieu", "gia", "bo_loc", "ly_do"])
    for s in items:
        w.writerow([s["time_text"], s["symbol"], s["direction"], "" if s["price"] is None else f"{s['price']:.0f}",
                    s["filter_name"], s["reason"]])
    return buf.getvalue()
