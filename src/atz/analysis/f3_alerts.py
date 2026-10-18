"""F3 Cảnh báo — decision-support phrases từ nến ngày (T-230).

Chỉ UI / optional cùng format Telegram. Không Intent / order / broker.
Spec: docs/specs/F3_ALERTS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd

from analysis.technical import bollinger, ichimoku, sma
from config import BB_LENGTH, BB_STD, ICHIMOKU_DISPLACEMENT, ICHIMOKU_KIJUN, ICHIMOKU_SENKOU_B, ICHIMOKU_TENKAN, SUPPORT_BAND

# Open Q §11 defaults (T-230):
# - So level bằng close ngày (không last RT).
# - Tolerance: 0 cho MA/BB/mây; SUPPORT_BAND tương đối cho swing.
SWING_LOOKBACK = 60


@dataclass(frozen=True)
class AlertPhrase:
    symbol: str
    level_kind: str
    direction: str  # "support" | "resist" | "trend"
    text: str
    level: float | None = None
    session_date: date | None = None

    @property
    def dedup_key(self) -> tuple[str, str, str, str]:
        day = self.session_date.isoformat() if self.session_date else ""
        return (self.symbol.upper(), self.level_kind, self.direction, day)


def format_price(value: float) -> str:
    if value >= 1000:
        return f"{value:.0f}"
    if value >= 100:
        return f"{value:.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".") if value < 10 else f"{value:.1f}"


def _cross_down(prev: float, close: float, level: float, tol: float = 0.0) -> bool:
    threshold = level - tol
    return prev >= threshold and close < threshold


def _cross_up(prev: float, close: float, level: float, tol: float = 0.0) -> bool:
    threshold = level + tol
    return prev <= threshold and close > threshold


def day_trend(close: pd.Series, ma20: pd.Series) -> str:
    """tăng | giảm | sideway — rule đơn giản close vs MA20 + dốc MA20."""
    if len(close) < 2 or pd.isna(ma20.iloc[-1]) or pd.isna(ma20.iloc[-2]):
        return "sideway"
    last = float(close.iloc[-1])
    ma_now = float(ma20.iloc[-1])
    ma_prev = float(ma20.iloc[-2])
    rising = ma_now > ma_prev
    falling = ma_now < ma_prev
    if last > ma_now and rising:
        return "tăng"
    if last < ma_now and falling:
        return "giảm"
    return "sideway"


def _kind_short_label(kind: str) -> str:
    """Nhãn gọn khi gộp nhiều mốc cùng giá (T-233 P2-b)."""
    return {
        "BB_upper": "biên trên band",
        "BB_mid": "band giữa",
        "BB_lower": "biên dưới band",
        "CLOUD_upper": "mây",
        "CLOUD_lower": "mây",
        "SWING_LOW": "vùng đáy",
        "SWING_HIGH": "vùng đỉnh cũ",
    }.get(kind, kind)


def _support_text(kind: str, price: float) -> str:
    p = format_price(price)
    if kind.startswith("MA"):
        return f"giảm thủng hỗ trợ {kind} {p}"
    if kind == "BB_upper":
        return f"giảm thủng biên trên band {p}"
    if kind == "BB_mid":
        return f"giảm thủng band giữa {p}"
    if kind == "BB_lower":
        return f"giá đi ra ngoài band dưới {p}"
    if kind == "CLOUD_upper":
        return f"thủng biên trên mây (giá đi vào trong mây) {p}"
    if kind == "CLOUD_lower":
        return f"giá đi xuống dưới mây {p}"
    if kind == "SWING_LOW":
        return f"giảm thủng vùng hỗ trợ đáy {p}"
    if kind == "SWING_HIGH":
        # Đỉnh cũ đóng vai trò hỗ trợ khi thủng — tránh «hỗ trợ đỉnh» gây hiểu nhầm.
        return f"giảm thủng vùng đỉnh cũ {p}"
    return f"giảm thủng hỗ trợ {kind} {p}"


def _resist_text(kind: str, price: float) -> str:
    p = format_price(price)
    label = _kind_short_label(kind)
    if kind.startswith("CLOUD"):
        label = "biên trên mây" if kind == "CLOUD_upper" else "biên dưới mây"
    return f"vượt kháng cự {label} {p}"


def _levels_at(work: pd.DataFrame) -> tuple[dict[str, float], pd.Series]:
    close = work["close"]
    high = work["high"]
    low = work["low"]
    ma20 = sma(close, 20)
    ma50 = sma(close, 50)
    ma100 = sma(close, 100)
    ma200 = sma(close, 200)
    bb_l, bb_m, bb_u = bollinger(close, BB_LENGTH, BB_STD)
    _, _, span_a, span_b = ichimoku(
        high, low, ICHIMOKU_TENKAN, ICHIMOKU_KIJUN, ICHIMOKU_SENKOU_B, ICHIMOKU_DISPLACEMENT
    )
    i = -1
    cloud_a = float(span_a.iloc[i]) if pd.notna(span_a.iloc[i]) else None
    cloud_b = float(span_b.iloc[i]) if pd.notna(span_b.iloc[i]) else None
    levels: dict[str, float] = {}
    for kind, series in (
        ("MA20", ma20),
        ("MA50", ma50),
        ("MA100", ma100),
        ("MA200", ma200),
        ("BB_upper", bb_u),
        ("BB_mid", bb_m),
        ("BB_lower", bb_l),
    ):
        value = series.iloc[i]
        if pd.notna(value):
            levels[kind] = float(value)
    if cloud_a is not None and cloud_b is not None:
        levels["CLOUD_upper"] = max(cloud_a, cloud_b)
        levels["CLOUD_lower"] = min(cloud_a, cloud_b)
    window = work.tail(SWING_LOOKBACK)
    if not window.empty:
        levels["SWING_LOW"] = float(window["low"].min())
        levels["SWING_HIGH"] = float(window["high"].max())
    return levels, ma20


def build_alert_phrases(symbol: str, bars: pd.DataFrame, session_date: date | None = None) -> list[AlertPhrase]:
    """bars_D → list AlertPhrase (xu hướng + cross support/resist)."""
    code = symbol.strip().upper()
    if bars is None or bars.empty or len(bars) < 25:
        return []
    work = bars.copy()
    for col in ("open", "high", "low", "close"):
        if col not in work.columns:
            return []
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=["close", "high", "low"])
    if len(work) < 25:
        return []

    levels, ma20 = _levels_at(work)
    close = work["close"]
    prev = float(close.iloc[-2])
    last = float(close.iloc[-1])
    trend = day_trend(close, ma20)
    phrases: list[AlertPhrase] = [
        AlertPhrase(
            symbol=code,
            level_kind="TREND",
            direction="trend",
            text=f"xu hướng ngày: {trend}",
            level=None,
            session_date=session_date,
        )
    ]

    for kind, level in levels.items():
        if kind.startswith("_"):
            continue
        tol = abs(level) * SUPPORT_BAND if kind.startswith("SWING") else 0.0
        if _cross_down(prev, last, level, tol):
            phrases.append(
                AlertPhrase(
                    symbol=code,
                    level_kind=kind,
                    direction="support",
                    text=_support_text(kind, level),
                    level=level,
                    session_date=session_date,
                )
            )
        if _cross_up(prev, last, level, tol):
            phrases.append(
                AlertPhrase(
                    symbol=code,
                    level_kind=kind,
                    direction="resist",
                    text=_resist_text(kind, level),
                    level=level,
                    session_date=session_date,
                )
            )
    return phrases


def dedup_phrases(
    phrases: Iterable[AlertPhrase],
    already: set[tuple[str, str, str, str]] | None = None,
) -> list[AlertPhrase]:
    """UI dedup: 1 câu / (symbol, level_kind, direction, session_date)."""
    seen = set(already or ())
    out: list[AlertPhrase] = []
    for phrase in phrases:
        key = phrase.dedup_key
        if key in seen:
            continue
        seen.add(key)
        out.append(phrase)
    if already is not None:
        already.update(phrase.dedup_key for phrase in out)
    return out


def merge_same_price_phrases(phrases: Iterable[AlertPhrase]) -> list[AlertPhrase]:
    """Gộp mệnh đề cùng hướng + cùng mức giá → 1 câu (T-233 P2-b).

    VD: vượt kháng cự MA20/band giữa/mây cùng 19.5
    → `vượt kháng cự 19.5 (MA20, band giữa, mây)`.
    """
    items = list(phrases)
    buckets: dict[tuple[str, str], list[AlertPhrase]] = {}
    for phrase in items:
        if phrase.direction not in ("support", "resist") or phrase.level is None:
            continue
        key = (phrase.direction, format_price(float(phrase.level)))
        buckets.setdefault(key, []).append(phrase)

    emitted: set[tuple[str, str]] = set()
    out: list[AlertPhrase] = []
    for phrase in items:
        if phrase.direction not in ("support", "resist") or phrase.level is None:
            out.append(phrase)
            continue
        key = (phrase.direction, format_price(float(phrase.level)))
        if key in emitted:
            continue
        emitted.add(key)
        bucket = buckets[key]
        if len(bucket) == 1:
            out.append(bucket[0])
            continue
        labels: list[str] = []
        for item in bucket:
            label = _kind_short_label(item.level_kind)
            if label not in labels:
                labels.append(label)
        price = format_price(float(bucket[0].level))
        if phrase.direction == "resist":
            text = f"vượt kháng cự {price} ({', '.join(labels)})"
        else:
            text = f"giảm thủng hỗ trợ {price} ({', '.join(labels)})"
        out.append(
            AlertPhrase(
                symbol=bucket[0].symbol,
                level_kind="MERGED",
                direction=bucket[0].direction,
                text=text,
                level=bucket[0].level,
                session_date=bucket[0].session_date,
            )
        )
    return out


def join_phrases(phrases: Iterable[AlertPhrase]) -> str:
    texts = [p.text for p in phrases if p.text]
    return " · ".join(texts) if texts else "—"


def alert_column_for_bars(symbol: str, bars: pd.DataFrame | None, session_date: date | None = None) -> str:
    """Chuỗi cột UI. Thiếu bars (<25 nến) → —."""
    if not isinstance(bars, pd.DataFrame) or bars.empty or len(bars) < 25:
        return "—"
    # Cần MA200 cho full set; nếu thiếu vẫn cố phát xu hướng + level có sẵn.
    phrases = build_alert_phrases(symbol, bars, session_date=session_date)
    if not phrases:
        return "—"
    return join_phrases(merge_same_price_phrases(dedup_phrases(phrases)))
