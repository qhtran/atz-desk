"""Cache dòng tiền: file ghi hôm nay thì không gọi API."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import HN_ZONE
from datasource import flow as flow_mod
from datasource.flow import cache_is_fresh, load_flow, merge_net_vol
from tests.bars import frame


def test_fresh_cache_skips_the_api(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "FPT_foreign.csv"
    pd.DataFrame({"time": ["2026-10-14"], "net_vol": [123.0]}).to_csv(path, index=False)
    monkeypatch.setattr(flow_mod, "flow_path", lambda symbol, kind: path)
    calls: list[str] = []
    monkeypatch.setattr(flow_mod, "fetch_flow", lambda symbol, kind: calls.append(symbol) or pd.DataFrame())
    loaded = load_flow("FPT", "foreign")
    assert calls == []
    assert float(loaded["net_vol"].iloc[-1]) == 123.0
    assert cache_is_fresh(path) is True


def test_old_cache_calls_the_api_once(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "FPT_foreign.csv"
    pd.DataFrame({"time": ["2026-10-01"], "net_vol": [1.0]}).to_csv(path, index=False)
    old = datetime(2026, 10, 1, tzinfo=HN_ZONE).timestamp()
    path.touch()
    import os
    os.utime(path, (old, old))
    monkeypatch.setattr(flow_mod, "flow_path", lambda symbol, kind: path)
    fresh = pd.DataFrame({"time": ["2026-10-14"], "net_vol": [9.0]})
    calls: list[str] = []

    def _fetch(symbol: str, kind: str) -> pd.DataFrame:
        calls.append(kind)
        fresh.to_csv(path, index=False)
        return fresh

    monkeypatch.setattr(flow_mod, "fetch_flow", _fetch)
    loaded = load_flow("FPT", "foreign")
    assert calls == ["foreign"]
    assert float(loaded["net_vol"].iloc[-1]) == 9.0


def test_merge_aligns_net_vol_by_day() -> None:
    bars = frame([10.0, 11.0])
    flow = pd.DataFrame({"time": [bars["time"].iloc[-1]], "net_vol": [42.0]})
    merged = merge_net_vol(bars, flow, "foreign_net_vol")
    assert pd.isna(merged["foreign_net_vol"].iloc[0])
    assert float(merged["foreign_net_vol"].iloc[-1]) == 42.0
