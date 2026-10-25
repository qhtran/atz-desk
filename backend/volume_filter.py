"""Liquidity gate for priceboard publish (equities only).

Rule (3b):
- Indexes always pass.
- Equity volume == 0 → pass (pre-open / no prints yet).
- Equity 0 < volume < min for sàn → reject (hide).
- Equity volume >= min for sàn → pass.

Min volume: default HOSE; HNX/UPCOM có ngưỡng thấp hơn (config + fallback).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.board_universe import INDEX_SYMBOL_SET, exchange_for_symbol
from backend.observability import ERR_PB_CONFIG, log

DEFAULT_MIN_VOLUME = 500_000
DEFAULT_MIN_VOLUME_BY_EXCHANGE: dict[str, int] = {
    "HOSE": 500_000,
    "HNX": 50_000,
    "UPCOM": 50_000,
}

INDEX_SYMBOLS = INDEX_SYMBOL_SET

_CONFIG_LOGGED = False


@dataclass(frozen=True)
class VolumeFilterSettings:
    default: int
    by_exchange: dict[str, int]

    def threshold_for(self, tick: dict[str, Any]) -> int:
        ex = str(tick.get("exchange") or "").strip().upper()
        if ex in ("", "HSX"):
            ex = exchange_for_symbol(str(tick.get("symbol") or ""))
        elif ex == "UPX":
            ex = "UPCOM"
        return self.by_exchange.get(ex, self.default)


def _log_config_once(message: str, *, exc: Exception | None = None) -> None:
    global _CONFIG_LOGGED  # noqa: PLW0603
    if _CONFIG_LOGGED:
        return
    _CONFIG_LOGGED = True
    from backend.observability.logging import setup

    setup("worker")
    log(
        "worker",
        "CONFIG",
        message,
        logging.WARNING,
        error_code=ERR_PB_CONFIG,
        exc=exc,
    )


def _read_priceboard_yaml() -> dict[str, Any]:
    path = Path(os.getenv("PRICEBOARD_CONFIG", "/app/config/priceboard.yaml"))
    if not path.is_file():
        alt = Path(__file__).resolve().parent.parent / "config" / "priceboard.yaml"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return {}
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return dict(doc.get("priceboard") or {})
    except Exception as exc:  # noqa: BLE001
        _log_config_once("priceboard yaml unreadable", exc=exc)
        return {}


def load_volume_filter_settings() -> VolumeFilterSettings:
    default = DEFAULT_MIN_VOLUME
    by_ex = dict(DEFAULT_MIN_VOLUME_BY_EXCHANGE)

    env = (os.getenv("PRICEBOARD_MIN_VOLUME") or "").strip()
    if env.isdigit():
        default = max(0, int(env))

    pb = _read_priceboard_yaml()
    raw_default = pb.get("min_volume")
    if raw_default is not None and not env.isdigit():
        default = max(0, int(raw_default))

    raw_map = pb.get("min_volume_by_exchange")
    if isinstance(raw_map, dict):
        for key, val in raw_map.items():
            if val is None:
                continue
            ex = str(key).strip().upper()
            if ex == "HSX":
                ex = "HOSE"
            if ex == "UPX":
                ex = "UPCOM"
            try:
                by_ex[ex] = max(0, int(val))
            except (TypeError, ValueError):
                continue

    if env.isdigit():
        by_ex["HOSE"] = default

    return VolumeFilterSettings(default=default, by_exchange=by_ex)


def load_min_volume() -> int:
    """Legacy: ngưỡng mặc định (HOSE). Prefer load_volume_filter_settings()."""
    return load_volume_filter_settings().default


def is_index_row(tick: dict[str, Any]) -> bool:
    kind = str(tick.get("kind") or "").lower()
    if kind == "index":
        return True
    return str(tick.get("symbol") or "").upper() in INDEX_SYMBOLS


def passes_volume_filter(
    tick: dict[str, Any],
    settings: VolumeFilterSettings | int | None = None,
) -> bool:
    """Return True if tick should remain on the board / be published."""
    if is_index_row(tick):
        return True
    if isinstance(settings, int):
        threshold = settings
    elif isinstance(settings, VolumeFilterSettings):
        threshold = settings.threshold_for(tick)
    else:
        threshold = DEFAULT_MIN_VOLUME
    try:
        vol = int(tick.get("volume") or 0)
    except (TypeError, ValueError):
        vol = 0
    if vol == 0:
        return True
    return vol >= threshold
