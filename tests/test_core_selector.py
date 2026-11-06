"""Core selector: ADTV gate, quota 160/80/60, Redis cache."""

from __future__ import annotations

import json

from backend.core_selector import (
    CORE_SYMBOLS_KEY,
    DEFAULT_MIN_TRADED_VALUE,
    cache_core_symbols,
    select_core,
)


class _MemRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self.store[key] = value

    def get(self, key: str) -> str | None:
        return self.store.get(key)


def _rows() -> list[dict]:
    rows: list[dict] = [
        {"symbol": "THD", "exchange": "UPCOM", "adtv": 0},
        {"symbol": "AAA", "exchange": "HOSE", "adtv": 1_000_000_000},
        {"symbol": "FPT", "exchange": "HOSE", "adtv": 9_000_000_000},
        {"symbol": "VCB", "exchange": "HSX", "adtv": 8_000_000_000},
        {"symbol": "SHS", "exchange": "HNX", "adtv": 2_000_000_000},
        {"symbol": "PVS", "exchange": "HNX", "adtv": 500_000_000},
    ]
    for i in range(3):
        rows.append({"symbol": f"U{i}", "exchange": "UPCOM", "adtv": 1_500_000_000 + i})
    return rows


def test_zero_liquidity_and_below_floor_dropped():
    picked = select_core(_rows(), min_traded_value=DEFAULT_MIN_TRADED_VALUE)
    symbols = [row["symbol"] for row in picked]
    assert "THD" not in symbols
    assert "AAA" not in symbols
    assert "PVS" not in symbols
    assert symbols[0] == "FPT"
    assert "VCB" in symbols
    assert "SHS" in symbols
    assert symbols[-3:] == ["U2", "U1", "U0"]


def test_quota_caps_per_exchange():
    rows = []
    for i in range(170):
        rows.append({"symbol": f"H{i:03d}", "exchange": "HOSE", "adtv": 4_000_000_000 + i})
    for i in range(90):
        rows.append({"symbol": f"N{i:03d}", "exchange": "HNX", "adtv": 2_000_000_000 + i})
    for i in range(70):
        rows.append({"symbol": f"P{i:03d}", "exchange": "UPCOM", "adtv": 1_200_000_000 + i})
    rows.append({"symbol": "THD", "exchange": "UPCOM", "adtv": 0})
    picked = select_core(rows)
    by_ex: dict[str, int] = {"HOSE": 0, "HNX": 0, "UPCOM": 0}
    for row in picked:
        by_ex[row["exchange"]] += 1
    assert by_ex == {"HOSE": 160, "HNX": 80, "UPCOM": 60}
    assert len(picked) == 300
    assert all(row["symbol"] != "THD" for row in picked)
    hose = [row["symbol"] for row in picked if row["exchange"] == "HOSE"]
    assert hose[0] == "H169"


def test_redis_cache_roundtrip_excludes_thd():
    picked = select_core(_rows())
    client = _MemRedis()
    cache_core_symbols(client, picked, min_traded_value=DEFAULT_MIN_TRADED_VALUE)
    payload = json.loads(client.get(CORE_SYMBOLS_KEY) or "{}")
    assert "THD" not in payload["symbols"]
    assert payload["symbols"][0] == "FPT"
    assert payload["min_traded_value"]["HOSE"] == 3_000_000_000
    assert payload["quotas"] == {"HOSE": 160, "HNX": 80, "UPCOM": 60}
    floors = json.loads(client.get("priceboard:core:min_traded_value") or "{}")
    assert floors["UPCOM"] == 1_000_000_000
