"""Nút chạy lọc làm mới nến và chỉ tải dòng tiền khi filter đó được bật."""

from __future__ import annotations

import pandas as pd

from engine import runner


def test_flow_is_loaded_only_for_the_selected_kind(monkeypatch) -> None:
    bars = pd.DataFrame(
        {
            "time": ["2026-10-14"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [1.0],
        }
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(runner, "load_symbol_csv", lambda folder, symbol: None)

    def _bars(symbol: str, start: str) -> pd.DataFrame:
        del start
        return bars.copy()

    def _flow(symbol: str, kind: str) -> pd.DataFrame:
        calls.append((symbol, kind))
        return pd.DataFrame({"time": ["2026-10-14"], "net_vol": [5.0]})

    monkeypatch.setattr("datasource.client.load_bars", _bars)
    monkeypatch.setattr("datasource.client.load_index_bars", lambda: None)
    monkeypatch.setattr("datasource.flow.load_flow", _flow)
    frames, missing, index_bars = runner.load_frames_for_run(["fpt"], {"foreign"})
    assert missing == []
    assert index_bars is None
    assert calls == [("FPT", "foreign")]
    assert float(frames["FPT"]["foreign_net_vol"].iloc[-1]) == 5.0

    calls.clear()
    runner.load_frames_for_run(["FPT"], set())
    assert calls == []
