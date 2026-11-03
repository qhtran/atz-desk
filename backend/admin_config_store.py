"""Admin control-plane: YAML base + JSON overlay (data/) — không ghi đè file YAML trong image."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from backend.core.trading_config import load_trading_config
from backend.engine.stream_listener import load_stream_alerts_config

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OVERLAY = Path(
    os.getenv("ADMIN_RUNTIME_CONFIG", str(_REPO_ROOT / "data" / "admin_runtime_config.json"))
)

# Whitelist fields admin được sửa (tránh arbitrary YAML injection).
_STREAM_KEYS = frozenset(
    {
        "enabled",
        "evaluate_interval_ms",
        "cooldown_sec",
        "ring_size",
        "max_alerts_per_tick",
        "rsi",
        "ma",
        "volume_spike",
        "risk_levels",
    }
)
_RSI_KEYS = frozenset({"length", "oversold", "overbought"})
_MA_KEYS = frozenset({"fast", "slow"})
_VOL_KEYS = frozenset({"lookback", "mult"})
_RISK_LVL_KEYS = frozenset({"high_below", "low_above"})
_RISK_KEYS = frozenset(
    {
        "stop_loss_pct",
        "take_profit_pct",
        "max_portfolio_risk_pct",
        "default_equity_pct",
        "max_positions",
    }
)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_overlay(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_OVERLAY
    if not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_overlay(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or DEFAULT_OVERLAY
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".admin_cfg_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _num(value: Any, *, lo: float | None = None, hi: float | None = None) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid number: {value!r}") from None
    if lo is not None and n < lo:
        raise ValueError(f"value {n} < {lo}")
    if hi is not None and n > hi:
        raise ValueError(f"value {n} > {hi}")
    return n


def _int(value: Any, *, lo: int | None = None, hi: int | None = None) -> int | None:
    n = _num(value, lo=lo, hi=hi)
    if n is None:
        return None
    return int(n)


def sanitize_stream_patch(patch: dict[str, Any] | None) -> dict[str, Any]:
    if not patch:
        return {}
    out: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in _STREAM_KEYS:
            continue
        if key == "enabled":
            out["enabled"] = bool(value)
        elif key == "evaluate_interval_ms":
            n = _int(value, lo=500, hi=60_000)
            if n is not None:
                out["evaluate_interval_ms"] = n
        elif key == "cooldown_sec":
            n = _int(value, lo=0, hi=86_400)
            if n is not None:
                out["cooldown_sec"] = n
        elif key == "ring_size":
            n = _int(value, lo=20, hi=500)
            if n is not None:
                out["ring_size"] = n
        elif key == "max_alerts_per_tick":
            n = _int(value, lo=1, hi=200)
            if n is not None:
                out["max_alerts_per_tick"] = n
        elif key == "rsi" and isinstance(value, dict):
            rsi: dict[str, Any] = {}
            if "length" in value:
                n = _int(value["length"], lo=2, hi=100)
                if n is not None:
                    rsi["length"] = n
            if "oversold" in value:
                n = _num(value["oversold"], lo=0, hi=100)
                if n is not None:
                    rsi["oversold"] = n
            if "overbought" in value:
                n = _num(value["overbought"], lo=0, hi=100)
                if n is not None:
                    rsi["overbought"] = n
            if rsi:
                out["rsi"] = rsi
        elif key == "ma" and isinstance(value, dict):
            ma: dict[str, Any] = {}
            if "fast" in value:
                n = _int(value["fast"], lo=1, hi=200)
                if n is not None:
                    ma["fast"] = n
            if "slow" in value:
                n = _int(value["slow"], lo=2, hi=400)
                if n is not None:
                    ma["slow"] = n
            if ma:
                out["ma"] = ma
        elif key == "volume_spike" and isinstance(value, dict):
            vol: dict[str, Any] = {}
            if "lookback" in value:
                n = _int(value["lookback"], lo=2, hi=200)
                if n is not None:
                    vol["lookback"] = n
            if "mult" in value:
                n = _num(value["mult"], lo=0.5, hi=20)
                if n is not None:
                    vol["mult"] = n
            if vol:
                out["volume_spike"] = vol
        elif key == "risk_levels" and isinstance(value, dict):
            rl: dict[str, Any] = {}
            if "high_below" in value:
                n = _num(value["high_below"], lo=0, hi=100)
                if n is not None:
                    rl["high_below"] = n
            if "low_above" in value:
                n = _num(value["low_above"], lo=0, hi=100)
                if n is not None:
                    rl["low_above"] = n
            if rl:
                out["risk_levels"] = rl
    return out


def sanitize_risk_patch(patch: dict[str, Any] | None) -> dict[str, Any]:
    if not patch:
        return {}
    out: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in _RISK_KEYS:
            continue
        if value is None or value == "":
            out[key] = None
            continue
        if key == "max_positions":
            out[key] = _int(value, lo=1, hi=500)
        else:
            out[key] = _num(value, lo=0, hi=100)
    return out


def base_stream_config() -> dict[str, Any]:
    return load_stream_alerts_config()


def base_risk_defaults() -> dict[str, Any]:
    cfg = load_trading_config()
    risk = (cfg.get("risk_tolerance") or {}).get("profiles") or {}
    profile = copy.deepcopy(risk.get("default") or {})
    sizing = copy.deepcopy(cfg.get("position_sizing") or {})
    return {
        "stop_loss_pct": profile.get("stop_loss_pct"),
        "take_profit_pct": profile.get("take_profit_pct"),
        "max_portfolio_risk_pct": profile.get("max_portfolio_risk_pct"),
        "default_equity_pct": sizing.get("default_equity_pct"),
        "max_positions": sizing.get("max_positions"),
    }


def effective_stream_config(overlay_path: Path | None = None) -> dict[str, Any]:
    overlay = _read_overlay(overlay_path)
    stream_ov = overlay.get("stream_alerts") if isinstance(overlay.get("stream_alerts"), dict) else {}
    return _deep_merge(base_stream_config(), stream_ov)


def effective_risk_config(overlay_path: Path | None = None) -> dict[str, Any]:
    overlay = _read_overlay(overlay_path)
    risk_ov = overlay.get("risk") if isinstance(overlay.get("risk"), dict) else {}
    return _deep_merge(base_risk_defaults(), risk_ov)


def get_control_plane(overlay_path: Path | None = None) -> dict[str, Any]:
    overlay = _read_overlay(overlay_path)
    return {
        "ok": True,
        "stream_alerts": effective_stream_config(overlay_path),
        "risk": effective_risk_config(overlay_path),
        "overlay_path": str(overlay_path or DEFAULT_OVERLAY),
        "has_overlay": bool(overlay),
    }


def put_control_plane(
    body: dict[str, Any],
    *,
    overlay_path: Path | None = None,
) -> dict[str, Any]:
    """Merge whitelist patch vào overlay JSON; trả control plane hiệu lực."""
    current = _read_overlay(overlay_path)
    stream_patch = sanitize_stream_patch(body.get("stream_alerts") if isinstance(body.get("stream_alerts"), dict) else {})
    risk_patch = sanitize_risk_patch(body.get("risk") if isinstance(body.get("risk"), dict) else {})

    if stream_patch:
        prev = current.get("stream_alerts") if isinstance(current.get("stream_alerts"), dict) else {}
        current["stream_alerts"] = _deep_merge(prev, stream_patch)
    if risk_patch:
        prev_r = current.get("risk") if isinstance(current.get("risk"), dict) else {}
        current["risk"] = _deep_merge(prev_r, risk_patch)

    _write_overlay(current, overlay_path)
    return get_control_plane(overlay_path)
