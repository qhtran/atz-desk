"""Core 300 selector — quota theo sàn + cổng ADTV (VNĐ).

Phân bổ: 160 HOSE / 80 HNX / 60 UPCOM.
Mã có ADTV <= 0 (trắng thanh khoản, ví dụ THD không có giao dịch) luôn bị loại,
kể cả khi admin hạ ngưỡng về 0.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

DEFAULT_QUOTAS: dict[str, int] = {"HOSE": 160, "HNX": 80, "UPCOM": 60}
DEFAULT_MIN_TRADED_VALUE: dict[str, int] = {
    "HOSE": 3_000_000_000,
    "HNX": 1_000_000_000,
    "UPCOM": 1_000_000_000,
}

CORE_SYMBOLS_KEY = "priceboard:core:symbols"
MIN_TRADED_VALUE_KEY = "priceboard:core:min_traded_value"

_EXCHANGES = ("HOSE", "HNX", "UPCOM")


def normalize_exchange(raw: Any) -> str:
    ex = str(raw or "").strip().upper()
    if ex in ("HSX", "HOSE"):
        return "HOSE"
    if ex == "HNX":
        return "HNX"
    if ex in ("UPX", "UPCOM"):
        return "UPCOM"
    return ""


def _priceboard_yaml_path() -> Path:
    env = (os.getenv("PRICEBOARD_CONFIG") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "config" / "priceboard.yaml"


def _read_priceboard_section() -> dict[str, Any]:
    path = _priceboard_yaml_path()
    if not path.is_file():
        return {}
    try:
        import yaml

        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        section = doc.get("priceboard") if isinstance(doc, dict) else None
        return dict(section) if isinstance(section, dict) else {}
    except Exception:
        return {}


def base_min_traded_value() -> dict[str, int]:
    """Ngưỡng ADTV (VNĐ) từ code default, ghi đè bằng ``priceboard.yaml``."""
    out = dict(DEFAULT_MIN_TRADED_VALUE)
    raw = _read_priceboard_section().get("min_traded_value")
    if isinstance(raw, dict):
        parsed = sanitize_min_traded_value(raw)
        out.update(parsed)
    return out


def sanitize_min_traded_value(patch: Mapping[str, Any] | None) -> dict[str, int]:
    if not isinstance(patch, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, value in patch.items():
        ex = normalize_exchange(key)
        if ex not in _EXCHANGES or value is None or value == "":
            continue
        try:
            n = int(float(value))
        except (TypeError, ValueError):
            continue
        if n < 0 or n > 10_000_000_000_000:
            continue
        out[ex] = n
    return out


def effective_min_traded_value(overlay: Mapping[str, Any] | None = None) -> dict[str, int]:
    out = base_min_traded_value()
    out.update(sanitize_min_traded_value(overlay))
    return out


def select_core(
    rows: list[Mapping[str, Any]],
    *,
    min_traded_value: Mapping[str, Any] | None = None,
    quotas: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Lọc ADTV rồi lấy top theo quota từng sàn (ADTV giảm dần, hòa thì mã A-Z)."""
    thresholds = effective_min_traded_value(min_traded_value)
    caps = dict(DEFAULT_QUOTAS)
    if quotas:
        for ex, cap in quotas.items():
            norm = normalize_exchange(ex)
            if norm in caps:
                caps[norm] = max(0, int(cap))

    buckets: dict[str, list[dict[str, Any]]] = {ex: [] for ex in caps}
    for row in rows:
        sym = str(row.get("symbol") or "").strip().upper()
        ex = normalize_exchange(row.get("exchange"))
        if not sym or ex not in buckets:
            continue
        try:
            adtv = float(row.get("adtv"))
        except (TypeError, ValueError):
            continue
        floor = float(thresholds.get(ex, 0))
        if adtv <= 0 or adtv < floor:
            continue
        buckets[ex].append({"symbol": sym, "exchange": ex, "adtv": adtv})

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ex in ("HOSE", "HNX", "UPCOM"):
        ranked = sorted(buckets.get(ex, []), key=lambda item: (-item["adtv"], item["symbol"]))
        kept = 0
        cap = caps.get(ex, 0)
        for item in ranked:
            if item["symbol"] in seen:
                continue
            seen.add(item["symbol"])
            selected.append(item)
            kept += 1
            if kept >= cap:
                break
    return selected


def render_core_yaml(
    selected: list[Mapping[str, Any]],
    *,
    min_traded_value: Mapping[str, int],
    quotas: Mapping[str, int] | None = None,
) -> str:
    caps = dict(DEFAULT_QUOTAS)
    if quotas:
        caps.update({normalize_exchange(k): int(v) for k, v in quotas.items() if normalize_exchange(k)})
    max_core = sum(caps.values())
    lines = [
        "# Core stream — Top 300 sau cổng ADTV (160 HOSE / 80 HNX / 60 UPCOM).",
        "# ADTV <= 0 bị loại. Ngưỡng runtime: priceboard.min_traded_value + admin overlay.",
        "version: 1",
        f"max_core: {max_core}",
        "min_traded_value:",
    ]
    for ex in ("HOSE", "HNX", "UPCOM"):
        lines.append(f"  {ex}: {int(min_traded_value[ex])}")
    lines.append("symbols:")
    for row in selected:
        lines.append(f"  - {row['symbol']}")
    lines.append("")
    return "\n".join(lines)


def core_cache_payload(
    selected: list[Mapping[str, Any]],
    *,
    min_traded_value: Mapping[str, Any],
    quotas: Mapping[str, int] | None = None,
) -> str:
    caps = dict(DEFAULT_QUOTAS)
    if quotas:
        for ex, cap in quotas.items():
            norm = normalize_exchange(ex)
            if norm:
                caps[norm] = int(cap)
    body = {
        "symbols": [str(row["symbol"]) for row in selected],
        "min_traded_value": {ex: int(min_traded_value[ex]) for ex in ("HOSE", "HNX", "UPCOM")},
        "quotas": caps,
    }
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def cache_core_symbols(
    client: Any,
    selected: list[Mapping[str, Any]],
    *,
    min_traded_value: Mapping[str, Any],
    quotas: Mapping[str, int] | None = None,
) -> str:
    """Ghi JSON vào Redis ``priceboard:core:symbols``."""
    raw = core_cache_payload(selected, min_traded_value=min_traded_value, quotas=quotas)
    client.set(CORE_SYMBOLS_KEY, raw)
    client.set(
        MIN_TRADED_VALUE_KEY,
        json.dumps({ex: int(min_traded_value[ex]) for ex in ("HOSE", "HNX", "UPCOM")}, separators=(",", ":")),
    )
    return raw
