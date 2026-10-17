"""Redis idx:quote overlay cho bảng Chỉ số Việt Nam (Overview)."""

from __future__ import annotations

import json

import pandas as pd

from datasource.index_quotes import (
    apply_idx_quote_to_row,
    load_idx_quotes,
    overlay_vietnam_index_board,
)


class _FakeRedis:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def mget(self, keys):
        return [self.mapping.get(k) for k in keys]


def test_load_idx_quotes_parses_value_ref_pct():
    client = _FakeRedis(
        {
            "idx:quote:VNINDEX": json.dumps(
                {
                    "symbol": "VNINDEX",
                    "value": 1705.91,
                    "ref": 1698.35,
                    "change": 7.56,
                    "pct": 0.45,
                    "ts": 1_700_000_000.0,
                }
            ),
            "idx:quote:HNXINDEX": json.dumps({"symbol": "HNXINDEX", "value": 259.0}),  # thiếu ref
        }
    )
    got = load_idx_quotes(["VNINDEX", "HNXINDEX"], client=client)
    assert got["VNINDEX"]["value"] == 1705.91
    assert got["VNINDEX"]["pct"] == 0.45
    assert "HNXINDEX" not in got


def test_apply_idx_quote_to_row_overrides_ohlcv_semantics():
    row = {
        "Chỉ số": "VNIndex",
        "Tham chiếu": "1,719.40",  # close[-2] sai semantics
        "Đóng cửa": "1,704.87",
        "Tăng/giảm (điểm/%)": "-14.53 / -0.85%",
        "Mũi tên": "—",
    }
    quote = {"value": 1705.91, "ref": 1698.35, "change": 7.56, "pct": 0.45}
    assert apply_idx_quote_to_row(row, quote) is True
    assert row["Đóng cửa"] == "1,705.91"
    assert row["Tham chiếu"] == "1,698.35"
    assert "+7.56" in row["Tăng/giảm (điểm/%)"] and "+0.45%" in row["Tăng/giảm (điểm/%)"]


def test_overlay_vietnam_board_mock_quotes():
    board = pd.DataFrame(
        [
            {
                "Chỉ số": "VNIndex",
                "Tham chiếu": "1,719.40",
                "Đóng cửa": "1,704.87",
                "Tăng/giảm (điểm/%)": "-14.53 / -0.85%",
                "Mũi tên": "—",
            },
            {
                "Chỉ số": "VN30",
                "Tham chiếu": "1,800.00",
                "Đóng cửa": "1,850.00",
                "Tăng/giảm (điểm/%)": "+50.00 / +2.78%",
                "Mũi tên": "—",
            },
        ]
    )
    quotes = {
        "VNINDEX": {"value": 1705.91, "ref": 1698.35, "change": 7.56, "pct": 0.45, "ts": 99.0},
    }
    out = overlay_vietnam_index_board(board, quotes=quotes, use_live=False)
    assert out.iloc[0]["Đóng cửa"] == "1,705.91"
    assert "+0.45%" in out.iloc[0]["Tăng/giảm (điểm/%)"]
    # VN30 không có quote → giữ OHLCV
    assert out.iloc[1]["Đóng cửa"] == "1,850.00"
    assert out.attrs["index_price_source"] == "redis"
    assert out.attrs["index_redis_hits"] == 1
    assert out.attrs["index_quote_ts"] == 99.0
