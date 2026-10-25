from backend.board_universe import (
    INDEX_BOARD_SYMBOLS,
    default_watchlist,
    exchange_for_symbol,
    mock_equity_seeds,
    symbols_for_market_tab,
)


def test_exchange_for_symbol_splits_boards():
    assert exchange_for_symbol("FPT") == "HOSE"
    assert exchange_for_symbol("VCI") == "HOSE"
    assert exchange_for_symbol("SHS") == "HNX"
    assert exchange_for_symbol("ART") == "UPCOM"


def test_default_watchlist_includes_all_segments():
    wl = default_watchlist()
    assert "FPT" in wl
    assert "VCI" in wl
    assert "SHS" in wl
    assert "ART" in wl


def test_index_board_symbols_include_vn30_futures():
    assert "VN30F1M" in INDEX_BOARD_SYMBOLS
    assert "VN30F2M" in INDEX_BOARD_SYMBOLS


def test_foreign_market_tab_uses_full_watchlist():
    foreign = symbols_for_market_tab("FOREIGN")
    wl = default_watchlist()
    assert set(foreign) == set(wl)
    assert "FPT" in foreign and "SHS" in foreign


def test_mock_equity_seeds_has_hnx_upcom():
    rows = mock_equity_seeds(target=70)
    exchanges = {ex for _, _, ex in rows}
    assert "HOSE" in exchanges
    assert "HNX" in exchanges
    assert "UPCOM" in exchanges
    hose_only_vn30 = sum(1 for sym, _, ex in rows if ex == "HOSE" and sym in {
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
    })
    hose_extra = sum(1 for sym, _, ex in rows if ex == "HOSE" and sym == "VCI")
    assert hose_extra >= 1
    assert len(rows) >= 50

