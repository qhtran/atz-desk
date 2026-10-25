"""Danh sách mã theo sàn cho priceboard dev (mock + SSI watchlist mặc định)."""

from __future__ import annotations

from typing import Literal

Exchange = Literal["HOSE", "HNX", "UPCOM"]

# Chỉ số / HĐTL trên index-bar iBoard (parity config/index.yaml)
INDEX_BOARD_SYMBOLS: tuple[str, ...] = (
    "VNINDEX",
    "VN30",
    "VN30F1M",
    "VN30F2M",
    "HNXINDEX",
    "UPCOMINDEX",
)
INDEX_SYMBOL_SET = frozenset(INDEX_BOARD_SYMBOLS)

# HĐTL: index-bar + một dòng depth (parse/merge như equity, không indexsummary)
FUTURES_BOARD_SYMBOLS: tuple[str, ...] = ("VN30F1M", "VN30F2M")
FUTURES_SYMBOL_SET = frozenset(FUTURES_BOARD_SYMBOLS)

# Ref mặc định khi Redis chưa có tick (khớp backend/ssi_live INDEX_SEED)
INDEX_DEFAULT_REFS: dict[str, float] = {
    "VNINDEX": 1285.4,
    "VN30": 1342.1,
    "VN30F1M": 1847.0,
    "VN30F2M": 1850.2,
    "HNXINDEX": 238.6,
    "UPCOMINDEX": 95.2,
}

VN30_SYMBOLS: tuple[str, ...] = (
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "LPB", "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
)

# HOSE nhưng không thuộc VN30 — để tab HOSE ≠ tab VN30 khi mock/SSI
HOSE_EXTRA_SYMBOLS: tuple[str, ...] = (
    "VCI", "GEX", "PDR", "HSG", "NKG", "DGC", "DIG", "DXG", "HCM", "KDH",
    "NLG", "PNJ", "POW", "REE", "TCH", "VND", "VGC", "VPI", "VSH", "GMD",
)

HNX_SYMBOLS: tuple[str, ...] = (
    "SHS", "PVS", "TIG", "IDC", "VCS", "CEO", "NRC", "LAS", "SHN", "BVS",
    "DTD", "HUT", "KLF", "PLC", "VIG",
)

UPCOM_SYMBOLS: tuple[str, ...] = (
    "ART", "QBS", "VE4", "VNR", "SMT", "LAI", "HAT", "VGP", "KTC", "DTK",
    "VLA", "BRS", "CLX", "SDG", "VCR",
)

VN30_SET = frozenset(VN30_SYMBOLS)


def exchange_for_symbol(symbol: str) -> Exchange:
    sym = str(symbol or "").strip().upper()
    if sym in VN30_SET or sym in HOSE_EXTRA_SYMBOLS:
        return "HOSE"
    if sym in HNX_SYMBOLS:
        return "HNX"
    if sym in UPCOM_SYMBOLS:
        return "UPCOM"
    return "HOSE"


def symbols_for_market_tab(market: str) -> list[str]:
    """Mã equity theo tab iBoard (không index)."""
    tab = str(market or "HOSE").strip().upper()
    if tab == "FOREIGN":
        return default_watchlist()
    if tab in ("VN30F1M", "VN30F2M"):
        return [tab]
    if tab == "VN30":
        return list(VN30_SYMBOLS)
    if tab == "HNX":
        return list(HNX_SYMBOLS)
    if tab == "UPCOM":
        return list(UPCOM_SYMBOLS)
    return list(dict.fromkeys([*VN30_SYMBOLS, *HOSE_EXTRA_SYMBOLS]))


def default_watchlist() -> list[str]:
    """Mã equity subscribe SSI / seed mock khi config.symbols rỗng."""
    out: list[str] = []
    seen: set[str] = set()
    for sym in (*VN30_SYMBOLS, *HOSE_EXTRA_SYMBOLS, *HNX_SYMBOLS, *UPCOM_SYMBOLS):
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def mock_equity_seeds(*, target: int = 70) -> list[tuple[str, int, Exchange]]:
    """(symbol, ref, exchange) cho build_seed mock."""
    target = max(50, min(80, target))
    rows: list[tuple[str, int, Exchange]] = []
    seen: set[str] = set()

    def add(sym: str, ref: int, ex: Exchange) -> None:
        if sym in seen or len(rows) >= target:
            return
        seen.add(sym)
        rows.append((sym, ref, ex))

    refs_vn30 = {
        "ACB": 24850, "FPT": 118500, "HPG": 27800, "VCB": 92500, "VIC": 41500,
    }
    for sym in VN30_SYMBOLS:
        ref = refs_vn30.get(sym, 20_000 + (sum(ord(c) for c in sym) * 97) % 150_000)
        add(sym, int(round(ref / 50) * 50), "HOSE")

    for i, sym in enumerate(HOSE_EXTRA_SYMBOLS):
        ref = 8_000 + i * 1_150
        add(sym, int(round(ref / 50) * 50), "HOSE")

    for i, sym in enumerate(HNX_SYMBOLS):
        ref = 5_000 + i * 800
        add(sym, int(round(ref / 50) * 50), "HNX")

    for i, sym in enumerate(UPCOM_SYMBOLS):
        ref = 3_000 + i * 500
        add(sym, max(1_050, int(round(ref / 50) * 50)), "UPCOM")

    n = 0
    while len(rows) < target:
        chars = []
        x = n
        for _ in range(3):
            chars.append(chr(ord("A") + (x % 26)))
            x //= 26
        sym = "".join(reversed(chars))
        n += 1
        if sym in seen:
            continue
        ex: Exchange = ("HOSE", "HNX", "UPCOM")[n % 3]
        ref = 5_000 + (sum(ord(c) for c in sym) * 137) % 180_000
        add(sym, int(round(ref / 50) * 50), ex)

    return rows
