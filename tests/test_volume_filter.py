"""Unit tests for priceboard volume liquidity gate."""

from backend.volume_filter import passes_volume_filter


def test_index_always_passes_even_zero_volume():
    assert passes_volume_filter({"symbol": "VNINDEX", "kind": "index", "volume": 0}, 500_000)
    assert passes_volume_filter({"symbol": "VN30", "kind": "index", "volume": 100}, 500_000)


def test_equity_zero_volume_passes():
    assert passes_volume_filter({"symbol": "FPT", "kind": "equity", "volume": 0}, 500_000)


def test_equity_below_min_rejected():
    assert not passes_volume_filter({"symbol": "FPT", "kind": "equity", "volume": 499_999}, 500_000)


def test_equity_at_or_above_min_passes():
    assert passes_volume_filter({"symbol": "FPT", "kind": "equity", "volume": 500_000}, 500_000)
    assert passes_volume_filter({"symbol": "FPT", "kind": "equity", "volume": 2_000_000}, 500_000)
