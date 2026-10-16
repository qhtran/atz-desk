"""Chấm CANSLIM từ dữ liệu sẵn có. Hàm thuần: nhận số liệu, trả các dòng checklist.
Chữ nào thiếu dữ liệu trả status 'N/A' thay vì đoán."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import config as C

T = C.CANSLIM


def _row(letter, rule, actual, passed, note=""):
    status = "N/A" if passed is None else ("✓" if passed else "✗")
    return {"Chữ": letter, "Tiêu chí": rule, "Thực tế": actual, "Đạt": status, "Ghi chú": note}


def check_c(eps_growth_pct, period="—"):
    return _row("C", f"EPS quý tăng > {T['C_EPS_GROWTH']:.0f}% so cùng kỳ",
                "—" if eps_growth_pct is None else f"{eps_growth_pct:.1f}% ({period})",
                None if eps_growth_pct is None else eps_growth_pct > T["C_EPS_GROWTH"])


def check_a(roe_pct):
    return _row("A", f"ROE quý mới nhất > {T['A_ROE']:.0f}%",
                "—" if roe_pct is None else f"{roe_pct:.1f}%",
                None if roe_pct is None else roe_pct > T["A_ROE"],
                "Thay cho tăng trưởng EPS năm (chưa lấy số liệu năm).")


def check_n(w: pd.DataFrame):
    hi = float(w["high"].tail(250).max())
    price = float(w["close"].iloc[-1])
    ratio = price / hi if hi else 0
    days = len(w.tail(250))
    note = "Đủ 52 tuần." if days >= 240 else f"Chỉ có {days} phiên, đỉnh tính trên khoảng này."
    return _row("N", f"Giá ≥ {T['N_NEAR_HIGH'] * 100:.0f}% đỉnh 52 tuần (hoặc lập đỉnh mới)",
                f"{ratio * 100:.1f}% đỉnh {hi:.2f}", ratio >= T["N_NEAR_HIGH"], note)


def check_s(w: pd.DataFrame):
    n = T["S_VOLUME_AVG"]
    vol = w["volume"].astype(float)
    if len(vol) < n + 1:
        return _row("S", "KL phiên cuối bùng nổ", "—", None, "Chưa đủ phiên.")
    avg = float(vol.iloc[-n - 1:-1].mean())
    ratio = float(vol.iloc[-1]) / avg if avg else 0
    up_day = float(w["close"].iloc[-1]) >= float(w["close"].iloc[-2])
    return _row("S", f"KL phiên cuối ≥ {T['S_VOLUME_SURGE']}× TB {n} phiên, phiên tăng",
                f"{ratio:.2f}× ({'tăng' if up_day else 'giảm'})",
                ratio >= T["S_VOLUME_SURGE"] and up_day)


def return_3m(w: pd.DataFrame) -> float | None:
    close = w["close"].astype(float)
    if len(close) < 63:
        return None
    return float(close.iloc[-1] / close.iloc[-63] - 1) * 100


def universe_returns(bars_dir: Path = C.BARS_DIR, universe=C.UNIVERSE) -> dict[str, float]:
    """RS 3 tháng (~63 phiên) của các mã trong danh sách quét, đọc từ cache data/ohlcv (không gọi mạng)."""
    out = {}
    for sym in universe:
        path = bars_dir / f"{sym}.csv"
        if not path.exists():
            continue
        try:
            r = return_3m(pd.read_csv(path).sort_values("time"))
        except Exception:
            r = None
        if r is not None:
            out[sym] = r
    return out


def check_l(own_ret, peer_returns: dict[str, float], index_ret=None):
    if own_ret is None or len(peer_returns) < 5:
        return _row("L", "Cổ phiếu dẫn dắt (RS)", "—", None, "Chưa đủ dữ liệu so sánh.")
    values = list(peer_returns.values())
    pct = sum(v <= own_ret for v in values) / len(values) * 100
    note = f"So với {len(values)} mã trong danh sách quét."
    passed = pct >= T["L_RS_PERCENTILE"]
    if index_ret is not None:
        note += f" VNINDEX 3 tháng {index_ret:+.1f}%."
        passed = passed and own_ret > index_ret
    return _row("L", f"RS 3 tháng thuộc top {100 - T['L_RS_PERCENTILE']:.0f}%"
                + (" và vượt VNINDEX" if index_ret is not None else ""),
                f"{own_ret:+.1f}%, phân vị {pct:.0f}", passed, note)


def check_i():
    return _row("I", "Tổ chức / khối ngoại mua ròng", "—", None,
                "Chưa có nguồn dữ liệu sở hữu tổ chức trong app, không chấm.")


def check_m(index_bars: pd.DataFrame | None):
    n = T["M_MA"]
    if index_bars is None or len(index_bars) < n + 10:
        return _row("M", f"VNINDEX trên MA{n} và MA{n} dốc lên", "—", None,
                    "Không lấy được dữ liệu VNINDEX.")
    close = index_bars["close"].astype(float).reset_index(drop=True)
    ma = close.rolling(n).mean()
    above = close.iloc[-1] > ma.iloc[-1]
    rising = ma.iloc[-1] > ma.iloc[-10]
    return _row("M", f"VNINDEX trên MA{n} và MA{n} dốc lên",
                f"{close.iloc[-1]:.2f} vs MA{n} {ma.iloc[-1]:.2f}, {'dốc lên' if rising else 'đi ngang/xuống'}",
                bool(above and rising))


def score(rows: list[dict]) -> tuple[int, int]:
    """(số chữ đạt, số chữ chấm được — bỏ N/A)."""
    rated = [r for r in rows if r["Đạt"] != "N/A"]
    return sum(r["Đạt"] == "✓" for r in rated), len(rated)
