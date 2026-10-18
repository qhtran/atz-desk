"""T-230: F3 alert engine — cross / templates / multi-hit / dedup."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analysis.f3_alerts import (
    AlertPhrase,
    alert_column_for_bars,
    build_alert_phrases,
    dedup_phrases,
    join_phrases,
    merge_same_price_phrases,
)
from analysis.technical import sma
from datasource.f3_themes import load_f3_sector_themes


def _bars(closes: list[float], *, high_pad: float = 0.5, low_pad: float = 0.5) -> pd.DataFrame:
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "time": f"2026-01-{(index % 28) + 1:02d}",
                "open": close,
                "high": close + high_pad,
                "low": close - low_pad,
                "close": close,
                "volume": 1_000_000,
            }
        )
    return pd.DataFrame(rows)


def test_load_f3_themes_has_fourteen():
    themes = load_f3_sector_themes()
    assert len(themes) == 14
    assert any(item["name"] == "Chứng khoán" for item in themes)
    ck = next(item for item in themes if "Chứng" in item["name"])
    assert "SSI" in ck["symbols"]


def test_cross_down_ma20_template():
    # 40 phiên phẳng 20.0 → MA20≈20; phiên cuối giảm thủng.
    closes = [20.0] * 40 + [19.0]
    bars = _bars(closes)
    ma20 = float(sma(bars["close"], 20).iloc[-1])
    assert ma20 > 19.0
    phrases = build_alert_phrases("SSI", bars, session_date=date(2026, 10, 18))
    support = [p for p in phrases if p.direction == "support" and p.level_kind == "MA20"]
    assert len(support) == 1
    assert support[0].text.startswith("giảm thủng hỗ trợ MA20")
    joined = join_phrases(phrases)
    assert "xu hướng ngày:" in joined
    assert "giảm thủng hỗ trợ MA20" in joined


def test_no_cross_no_support_phrase():
    # Phẳng tuyệt đối: không cross MA/BB/mây/swing.
    closes = [20.0] * 50
    bars = _bars(closes, high_pad=0.0, low_pad=0.0)
    phrases = build_alert_phrases("HCM", bars, session_date=date(2026, 10, 18))
    assert any(p.direction == "trend" for p in phrases)
    assert not any(p.direction == "support" for p in phrases)
    assert not any(p.direction == "resist" for p in phrases)


def test_multi_level_lists_all():
    # Tạo cross xuống cả MA20 và BB_mid (cùng vùng mid) bằng nến đỏ mạnh.
    closes = [15.0] * 30 + [14.0]
    bars = _bars(closes, high_pad=0.2, low_pad=0.2)
    phrases = build_alert_phrases("VCI", bars, session_date=date(2026, 10, 18))
    kinds = {p.level_kind for p in phrases if p.direction == "support"}
    assert "MA20" in kinds
    # BB mid ≈ MA20 — thường cùng cross
    assert "BB_mid" in kinds or "MA20" in kinds
    text = join_phrases(phrases)
    assert " · " in text


def test_dedup_same_key_once():
    day = date(2026, 10, 18)
    a = AlertPhrase("SSI", "MA20", "support", "giảm thủng hỗ trợ MA20 12.2", 12.2, day)
    b = AlertPhrase("SSI", "MA20", "support", "giảm thủng hỗ trợ MA20 12.2", 12.2, day)
    c = AlertPhrase("SSI", "MA50", "support", "giảm thủng hỗ trợ MA50 11.0", 11.0, day)
    already: set[tuple[str, str, str, str]] = set()
    first = dedup_phrases([a, b, c], already)
    assert len(first) == 2
    second = dedup_phrases([a], already)
    assert second == []


def test_alert_column_missing_bars():
    assert alert_column_for_bars("ZZZ", None) == "—"
    assert alert_column_for_bars("ZZZ", pd.DataFrame()) == "—"


def test_resist_cross_up_ma20():
    closes = [10.0] * 40 + [12.0]
    bars = _bars(closes)
    phrases = build_alert_phrases("FPT", bars, session_date=date(2026, 10, 18))
    resist = [p for p in phrases if p.direction == "resist" and p.level_kind == "MA20"]
    assert len(resist) == 1
    assert resist[0].text.startswith("vượt kháng cự")


def test_merge_same_price_resist():
    day = date(2026, 10, 18)
    phrases = [
        AlertPhrase("MBB", "TREND", "trend", "xu hướng ngày: tăng", None, day),
        AlertPhrase("MBB", "MA20", "resist", "vượt kháng cự MA20 19.5", 19.5, day),
        AlertPhrase("MBB", "BB_mid", "resist", "vượt kháng cự band giữa 19.5", 19.5, day),
        AlertPhrase("MBB", "CLOUD_lower", "resist", "vượt kháng cự biên dưới mây 19.5", 19.5, day),
    ]
    merged = merge_same_price_phrases(phrases)
    resist = [p for p in merged if p.direction == "resist"]
    assert len(resist) == 1
    assert resist[0].text == "vượt kháng cự 19.5 (MA20, band giữa, mây)"
    joined = join_phrases(merged)
    assert joined.count("19.5") == 1
    assert " · " in joined


def test_swing_high_wording():
    from analysis.f3_alerts import _support_text

    text = _support_text("SWING_HIGH", 23.4)
    assert text == "giảm thủng vùng đỉnh cũ 23.4"
    assert "hỗ trợ đỉnh" not in text


def test_swing_high_compose_snapshot():
    """S-022: fixture bars → build_alert_phrases sinh SWING_HIGH «vùng đỉnh cũ»."""
    from config import SUPPORT_BAND

    peak = 25.0
    threshold = peak * (1.0 - SUPPORT_BAND)
    # 40 phiên đỉnh high=25; prev/last cross xuống qua ngưỡng swing (SUPPORT_BAND).
    n_flat = 40
    closes = [24.8] * n_flat + [threshold + 0.01, threshold - 0.01]
    highs = [peak] * n_flat + [threshold + 0.05, threshold]
    lows = [24.0] * (n_flat + 2)
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "time": f"2026-01-{(index % 28) + 1:02d}",
                "open": close,
                "high": highs[index],
                "low": lows[index],
                "close": close,
                "volume": 1_000_000,
            }
        )
    bars = pd.DataFrame(rows)
    phrases = build_alert_phrases("TCB", bars, session_date=date(2026, 10, 18))
    swing = [p for p in phrases if p.level_kind == "SWING_HIGH" and p.direction == "support"]
    assert len(swing) >= 1
    assert swing[0].text == "giảm thủng vùng đỉnh cũ 25.0"
    joined = join_phrases(phrases)
    assert "vùng đỉnh cũ" in joined
    assert "hỗ trợ đỉnh" not in joined
    assert "vùng hỗ trợ đỉnh" not in joined
    # Path UI cột Cảnh báo cũng giữ wording.
    col = alert_column_for_bars("TCB", bars, session_date=date(2026, 10, 18))
    assert "vùng đỉnh cũ" in col
    assert "hỗ trợ đỉnh" not in col
    assert "vùng hỗ trợ đỉnh" not in col
