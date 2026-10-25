"""WS snapshot index stubs."""

from __future__ import annotations

from backend.redis_listener import merge_index_stubs


def test_merge_index_stubs_adds_vn30_futures():
    rows = [
        {"symbol": "VNINDEX", "kind": "index", "last": 1285.0, "volume": 0},
        {"symbol": "VN30", "kind": "index", "last": 1340.0, "volume": 0},
        {"symbol": "HNXINDEX", "kind": "index", "last": 238.0, "volume": 0},
        {"symbol": "UPCOMINDEX", "kind": "index", "last": 95.0, "volume": 0},
    ]
    merged = merge_index_stubs(rows)
    syms = {str(r["symbol"]).upper() for r in merged}
    assert "VN30F1M" in syms
    assert "VN30F2M" in syms
    f1 = next(r for r in merged if r["symbol"] == "VN30F1M")
    assert f1["kind"] == "index"
    assert float(f1["last"]) == 1847.0
    assert f1.get("source") == "index_stub"


def test_merge_index_stubs_keeps_live_rows():
    rows = [
        {"symbol": "VN30F1M", "kind": "index", "last": 1900.0, "volume": 0, "source": "SSI_WS"},
    ]
    merged = merge_index_stubs(rows)
    f1 = next(r for r in merged if r["symbol"] == "VN30F1M")
    assert float(f1["last"]) == 1900.0
    assert f1.get("source") == "SSI_WS"
