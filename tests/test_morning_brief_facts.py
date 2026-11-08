"""Session facts collectors (OHLCV + Redis mock + vnstock stub)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.morning_brief_facts import (
    build_session_facts,
    collect_redis_board_stats,
    format_facts_macro_block,
    vni_from_bars,
)


def _write_bars(path: Path, symbol: str, closes: list[float]) -> None:
    rows = []
    for i, close in enumerate(closes):
        day = 1 + (i % 28)
        month = 1 + (i // 28) % 12
        year = 2024 + (i // 28) // 12
        rows.append(
            {
                "time": f"{year}-{month:02d}-{day:02d}",
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1_000_000,
            }
        )
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path / f"{symbol}.csv", index=False)


def test_vni_from_bars_change(tmp_path: Path):
    _write_bars(tmp_path, "VNINDEX", [100.0, 102.5, 110.0])
    vni = vni_from_bars(tmp_path, "VNINDEX")
    assert vni["close"] == 110.0
    assert vni["prev_close"] == 102.5
    assert vni["chg_pts"] == 7.5
    assert vni["direction"] == "tăng"
    assert vni["source"] == "ohlcv"


def test_redis_board_stats_with_fake_client():
    class _FakeRedis:
        def hgetall(self, _key):
            return {
                "HPG": (
                    '{"symbol":"HPG","kind":"stock","last":28000,"volume":1000,'
                    '"foreignNetValue":-5000000000}'
                ),
                "VNINDEX": '{"symbol":"VNINDEX","kind":"index","last":1700,"volume":0}',
            }

        def close(self):
            return None

    stats = collect_redis_board_stats(redis_factory=lambda *_a, **_k: _FakeRedis())
    assert stats["equity_count"] == 1
    assert stats["nn_count"] == 1
    assert stats["gtgd_vnd"] == 28000 * 1000
    assert stats["nn_net_vnd"] == -5_000_000_000
    assert stats["source"] == "redis_board"


def test_build_session_facts_prefers_vnstock_nn(tmp_path: Path):
    _write_bars(tmp_path, "VNINDEX", [1700.0, 1740.0])

    def fake_vnstock():
        return {
            "nn_net_vnd": -239_000_000_000,
            "prop_net_vnd": 254_000_000_000,
            "source": "vnstock_insights",
            "error": None,
        }

    class _EmptyRedis:
        def hgetall(self, _key):
            return {}

        def close(self):
            return None

    facts = build_session_facts(
        bars_dir=tmp_path,
        index_symbol="VNINDEX",
        index_tech={"M": "trên mây", "W": "trong mây", "D": "BB giữa"},
        redis_factory=lambda *_a, **_k: _EmptyRedis(),
        vnstock_collector=fake_vnstock,
        enable_vnstock=True,
    )
    assert facts["vni"]["close"] == 1740.0
    assert facts["nn_net_tn"] == -239.0
    assert facts["prop_net_tn"] == 254.0
    assert "NN bán ròng" in facts["foreign_prop_line"]
    assert "tự doanh mua ròng" in facts["foreign_prop_line"]
    block = format_facts_macro_block(facts)
    assert "### Khung Tháng (M)" in block
    assert "Kế hoạch giao dịch:" in block
