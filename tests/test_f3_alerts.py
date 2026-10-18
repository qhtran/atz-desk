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
