"""Map iBoard HĐTL symbols (VN30F1M/F2M) ↔ SSI contract codes (41I1…).

SSI X-Quote/X-Trade depth uses exchange contract codes, not mappingSymbol.
Override: ENV PRICEBOARD_FUTURES_CONTRACTS=VN30F1M:41I1GB000,VN30F2M:41I1GC000
or config priceboard.ssi.futures_contracts.
"""

from __future__ import annotations

import os
import re
from typing import Any

from backend.board_universe import FUTURES_BOARD_SYMBOLS

# Nearest/next month as of 2026-10 (rollover → cập nhật yaml/ENV).
_DEFAULT_CONTRACTS: dict[str, str] = {
    "VN30F1M": "41I1GB000",
    "VN30F2M": "41I1GC000",
}

_CONTRACT_RE = re.compile(r"^[0-9]{2}I1[A-Z]{2}[0-9]{3}$", re.I)


def parse_futures_contracts_env(raw: str | None) -> dict[str, str]:
    """Parse `VN30F1M:41I1GB000,VN30F2M:41I1GC000` → map."""
    out: dict[str, str] = {}
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        board, code = part.split(":", 1)
        board = board.strip().upper()
        code = code.strip().upper()
        if board and code:
            out[board] = code
    return out


def load_futures_contract_map(ssi_cfg: dict[str, Any] | None = None) -> dict[str, str]:
    """Board symbol → SSI contract code (chỉ FUTURES_BOARD_SYMBOLS)."""
    out = dict(_DEFAULT_CONTRACTS)
    cfg = dict(ssi_cfg or {})
    raw_map = cfg.get("futures_contracts")
    if isinstance(raw_map, dict):
        for k, v in raw_map.items():
            board = str(k or "").strip().upper()
            code = str(v or "").strip().upper()
            if board in FUTURES_BOARD_SYMBOLS and code:
                out[board] = code
    env_map = parse_futures_contracts_env(os.getenv("PRICEBOARD_FUTURES_CONTRACTS"))
    for board, code in env_map.items():
        if board in FUTURES_BOARD_SYMBOLS and code:
            out[board] = code
    return {b: out[b] for b in FUTURES_BOARD_SYMBOLS if out.get(b)}


def invert_contract_map(board_to_code: dict[str, str]) -> dict[str, str]:
    """Contract code → board symbol."""
    inv: dict[str, str] = {}
    for board, code in board_to_code.items():
        c = str(code or "").strip().upper()
        if c:
            inv[c] = board
    return inv


def looks_like_vn30_futures_contract(symbol: str) -> bool:
    return bool(_CONTRACT_RE.match(str(symbol or "").strip()))
