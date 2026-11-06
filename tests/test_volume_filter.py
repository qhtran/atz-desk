"""Unit tests for priceboard volume liquidity gate."""

from backend.volume_filter import VolumeFilterSettings, passes_volume_filter

HNX_UPCOM_FILTER = VolumeFilterSettings(
    default=500_000,
    by_exchange={"HOSE": 500_000, "HNX": 50_000, "UPCOM": 50_000},
)

# Off-core synthetic symbols (must not appear in priceboard_core_symbols.yaml)
OFF = "ZZZOFF1"
OFF_HNX = "ZZZOFF2"


def test_index_always_passes_even_zero_volume():
    assert passes_volume_filter({"symbol": "VNINDEX", "kind": "index", "volume": 0}, 500_000)
    assert passes_volume_filter({"symbol": "VN30", "kind": "index", "volume": 100}, 500_000)


def test_equity_zero_volume_passes():
    assert passes_volume_filter({"symbol": OFF, "kind": "equity", "volume": 0}, 500_000)


def test_offcore_equity_below_min_rejected():
    assert not passes_volume_filter({"symbol": OFF, "kind": "equity", "volume": 499_999}, 500_000)


def test_equity_at_or_above_min_passes():
    assert passes_volume_filter({"symbol": OFF, "kind": "equity", "volume": 500_000}, 500_000)
    assert passes_volume_filter({"symbol": OFF, "kind": "equity", "volume": 2_000_000}, 500_000)


def test_core_equity_bypasses_volume_gate():
    """Admin-First Core must stay on board even with thin session volume."""
    from backend.market_catalog import load_core_symbol_set

    core = load_core_symbol_set()
    assert core, "core yaml must load"
    sym = next(iter(core))
    assert passes_volume_filter(
        {"symbol": sym, "kind": "equity", "exchange": "HOSE", "volume": 1},
        HNX_UPCOM_FILTER,
    )


def test_hnx_lower_threshold_by_exchange():
    tick = {"symbol": OFF_HNX, "kind": "equity", "exchange": "HNX", "volume": 80_000}
    assert not passes_volume_filter(tick, 500_000)
    assert passes_volume_filter(tick, HNX_UPCOM_FILTER)


def test_hose_still_uses_high_threshold_in_multi_settings():
    tick = {"symbol": OFF, "kind": "equity", "exchange": "HOSE", "volume": 100_000}
    assert not passes_volume_filter(tick, HNX_UPCOM_FILTER)
