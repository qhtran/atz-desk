"""P0 master catalog + quote snapshot (no SSI WS)."""

from __future__ import annotations

from pathlib import Path

from backend.market_catalog import (
    clear_catalog_cache,
    get_catalog_symbol,
    list_core_catalog,
    load_core_symbol_set,
    search_catalog,
)
from backend.quote_snapshot import resolve_quote_snapshots


def setup_function() -> None:
    clear_catalog_cache()


def test_list_core_catalog_top240():
    core = load_core_symbol_set()
    assert len(core) >= 200
    items = list_core_catalog()
    assert len(items) == len(core)
    assert items[0]["symbol"]
    assert all(r.get("in_core") for r in items)
    assert {r["symbol"] for r in items} == set(core)
    capped = list_core_catalog(limit=30)
    assert len(capped) == 30


def test_catalog_includes_dbc_outside_core():
    core = load_core_symbol_set()
    assert "FPT" in core or "VCB" in core
    item = get_catalog_symbol("DBC")
    assert item is not None
    assert item["symbol"] == "DBC"
    assert item["exchange"] in ("HOSE", "HNX", "UPCOM")
    hits = search_catalog("DBC", limit=5)
    assert any(r["symbol"] == "DBC" for r in hits)
    assert hits[0]["symbol"] == "DBC"


def test_catalog_prefix_prefers_startswith():
    hits = search_catalog("FP", limit=10)
    assert hits
    assert hits[0]["symbol"].startswith("FP")


def test_snapshot_ohlcv_then_catalog(tmp_path: Path):
    (tmp_path / "DBC.csv").write_text("close,volume\n28.5,1000\n29.0,2000\n", encoding="utf-8")
    body = resolve_quote_snapshots(
        ["DBC", "ZZZZNOPE"],
        bars_dir=tmp_path,
        priceboard_rows={},
    )
    assert body["ok"] is True
    assert body["quotes"]["DBC"]["priced"] is True
    assert body["quotes"]["DBC"]["snap_source"] == "ohlcv"
    assert body["quotes"]["DBC"]["last"] == 29000
    assert "ZZZZNOPE" in body["missing"]


def test_snapshot_priceboard_wins(tmp_path: Path):
    body = resolve_quote_snapshots(
        ["FPT"],
        bars_dir=tmp_path,
        priceboard_rows={
            "FPT": {
                "symbol": "FPT",
                "last": 99500,
                "ref": 98000,
                "change_pct": 1.53,
                "source": "SSI_WS",
            }
        },
    )
    assert body["quotes"]["FPT"]["snap_source"] == "priceboard"
    assert body["quotes"]["FPT"]["last"] == 99500
