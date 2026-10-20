"""Liquidity gate for priceboard publish (equities only).

Rule (3b):
- Indexes always pass.
- Equity volume == 0 → pass (pre-open / no prints yet).
- Equity 0 < volume < min_volume → reject (hide).
- Equity volume >= min_volume → pass.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_MIN_VOLUME = 500_000

INDEX_SYMBOLS = frozenset({"VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"})


def load_min_volume() -> int:
    env = (os.getenv("PRICEBOARD_MIN_VOLUME") or "").strip()
    if env.isdigit():
        return max(0, int(env))
    path = Path(os.getenv("PRICEBOARD_CONFIG", "/app/config/priceboard.yaml"))
    if not path.is_file():
        alt = Path(__file__).resolve().parent.parent / "config" / "priceboard.yaml"
        path = alt if alt.is_file() else path
    if path.is_file():
        try:
            import yaml

            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            raw = (doc.get("priceboard") or {}).get("min_volume")
            if raw is not None:
                return max(0, int(raw))
        except Exception:  # noqa: BLE001
            pass
    return DEFAULT_MIN_VOLUME


def is_index_row(tick: dict[str, Any]) -> bool:
    kind = str(tick.get("kind") or "").lower()
    if kind == "index":
        return True
    return str(tick.get("symbol") or "").upper() in INDEX_SYMBOLS


def passes_volume_filter(tick: dict[str, Any], min_volume: int | None = None) -> bool:
    """Return True if tick should remain on the board / be published."""
    if is_index_row(tick):
        return True
    threshold = DEFAULT_MIN_VOLUME if min_volume is None else min_volume
    try:
        vol = int(tick.get("volume") or 0)
    except (TypeError, ValueError):
        vol = 0
    if vol == 0:
        return True
    return vol >= threshold
