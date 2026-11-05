"""Admin-first ops config for priceboard Core / volume / feature flags.

Persisted in ``data/admin_runtime_config.json`` under key ``priceboard``.
Invalid admin input is clamped or dropped — never crashes readers.
"""

from __future__ import annotations

import copy
from typing import Any

# Safe defaults (site stability first).
DEFAULT_PRICEBOARD_OPS: dict[str, Any] = {
    "core_allocation": {"HOSE": 160, "HNX": 80, "UPCOM": 60},
    "max_core": 300,
    "lookback_sessions": 20,
    "force_vn30": True,
    "min_volume": 500_000,
    "min_volume_by_exchange": {
        "HOSE": 500_000,
        "HNX": 50_000,
        "UPCOM": 50_000,
    },
    "maintenance_mode": False,
    "ondemand_sync_enabled": True,
    "reload_core_on_save": True,
}

# Hard ceilings — protect Redis / SSI WS memory.
HARD_MAX_CORE_TOTAL = 500
HARD_MAX_PER_EXCHANGE = 400
HARD_MIN_PER_EXCHANGE = 0
HARD_MIN_VOLUME = 0
HARD_MAX_VOLUME = 50_000_000


def _clamp_int(value: Any, *, lo: int, hi: int, default: int) -> tuple[int, str | None]:
    if value is None or value == "":
        return int(default), None
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return int(default), f"invalid int {value!r} → {default}"
    if n < lo:
        return lo, f"clamped {n} → {lo}"
    if n > hi:
        return hi, f"clamped {n} → {hi}"
    return n, None


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return bool(default)
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return bool(default)


def sanitize_priceboard_ops(
    patch: dict[str, Any] | None,
    *,
    base: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return (safe_ops, warnings). Never raises."""
    warnings: list[str] = []
    out = copy.deepcopy(base or DEFAULT_PRICEBOARD_OPS)
    if not isinstance(patch, dict) or not patch:
        return out, warnings

    if "core_allocation" in patch and isinstance(patch.get("core_allocation"), dict):
        alloc_in = patch["core_allocation"]
        alloc_out = dict(out.get("core_allocation") or {})
        for ex in ("HOSE", "HNX", "UPCOM"):
            if ex not in alloc_in:
                continue
            n, w = _clamp_int(
                alloc_in.get(ex),
                lo=HARD_MIN_PER_EXCHANGE,
                hi=HARD_MAX_PER_EXCHANGE,
                default=int(alloc_out.get(ex) or 0),
            )
            alloc_out[ex] = n
            if w:
                warnings.append(f"core_allocation.{ex}: {w}")
        out["core_allocation"] = alloc_out

    if "max_core" in patch:
        n, w = _clamp_int(
            patch.get("max_core"),
            lo=50,
            hi=HARD_MAX_CORE_TOTAL,
            default=int(out.get("max_core") or 300),
        )
        out["max_core"] = n
        if w:
            warnings.append(f"max_core: {w}")

    # Enforce sum(allocation) <= max_core <= HARD_MAX
    alloc = out.get("core_allocation") if isinstance(out.get("core_allocation"), dict) else {}
    hose = int(alloc.get("HOSE") or 0)
    hnx = int(alloc.get("HNX") or 0)
    up = int(alloc.get("UPCOM") or 0)
    total = hose + hnx + up
    max_core = int(out.get("max_core") or HARD_MAX_CORE_TOTAL)
    if total > HARD_MAX_CORE_TOTAL:
        # Scale down proportionally to hard cap
        scale = HARD_MAX_CORE_TOTAL / float(total)
        hose = max(0, int(hose * scale))
        hnx = max(0, int(hnx * scale))
        up = max(0, HARD_MAX_CORE_TOTAL - hose - hnx)
        out["core_allocation"] = {"HOSE": hose, "HNX": hnx, "UPCOM": up}
        total = hose + hnx + up
        warnings.append(f"core total scaled to {total} (hard max {HARD_MAX_CORE_TOTAL})")
    if total > max_core:
        out["max_core"] = total
        warnings.append(f"max_core raised to {total} to match allocation sum")
    elif max_core > HARD_MAX_CORE_TOTAL:
        out["max_core"] = HARD_MAX_CORE_TOTAL
        warnings.append(f"max_core capped at {HARD_MAX_CORE_TOTAL}")

    if "lookback_sessions" in patch:
        n, w = _clamp_int(
            patch.get("lookback_sessions"),
            lo=5,
            hi=120,
            default=int(out.get("lookback_sessions") or 20),
        )
        out["lookback_sessions"] = n
        if w:
            warnings.append(f"lookback_sessions: {w}")

    if "force_vn30" in patch:
        out["force_vn30"] = _as_bool(patch.get("force_vn30"), True)

    if "min_volume" in patch:
        n, w = _clamp_int(
            patch.get("min_volume"),
            lo=HARD_MIN_VOLUME,
            hi=HARD_MAX_VOLUME,
            default=int(out.get("min_volume") or 500_000),
        )
        out["min_volume"] = n
        if w:
            warnings.append(f"min_volume: {w}")

    if "min_volume_by_exchange" in patch and isinstance(patch.get("min_volume_by_exchange"), dict):
        mv = dict(out.get("min_volume_by_exchange") or {})
        for ex, val in patch["min_volume_by_exchange"].items():
            ex_u = str(ex or "").strip().upper()
            if ex_u == "HSX":
                ex_u = "HOSE"
            if ex_u.startswith("UPCO"):
                ex_u = "UPCOM"
            if ex_u not in ("HOSE", "HNX", "UPCOM"):
                warnings.append(f"min_volume_by_exchange: ignore {ex!r}")
                continue
            n, w = _clamp_int(
                val,
                lo=HARD_MIN_VOLUME,
                hi=HARD_MAX_VOLUME,
                default=int(mv.get(ex_u) or 0),
            )
            mv[ex_u] = n
            if w:
                warnings.append(f"min_volume_by_exchange.{ex_u}: {w}")
        out["min_volume_by_exchange"] = mv

    if "maintenance_mode" in patch:
        out["maintenance_mode"] = _as_bool(patch.get("maintenance_mode"), False)
    if "ondemand_sync_enabled" in patch:
        out["ondemand_sync_enabled"] = _as_bool(patch.get("ondemand_sync_enabled"), True)
    if "reload_core_on_save" in patch:
        out["reload_core_on_save"] = _as_bool(patch.get("reload_core_on_save"), True)

    return out, warnings


def effective_priceboard_ops(overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge overlay ``priceboard`` onto defaults with sanitize (never raises)."""
    raw = {}
    if isinstance(overlay, dict):
        pb = overlay.get("priceboard")
        if isinstance(pb, dict):
            raw = pb
    ops, _warnings = sanitize_priceboard_ops(raw, base=DEFAULT_PRICEBOARD_OPS)
    return ops
