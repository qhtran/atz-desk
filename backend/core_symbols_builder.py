"""Build ``config/priceboard_core_symbols.yaml`` with exchange-balanced Core.

Default allocation (Admin-First ops / ``config/core_allocation.yaml``):
  HOSE 160 · HNX 80 · UPCOM 60 (total 300).

Liquidity score = average(close * volume) over the last N OHLCV sessions.
Admin overlay (``data/admin_runtime_config.json`` → ``priceboard``) thắng YAML tĩnh.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from backend.board_universe import VN30_SYMBOLS

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ALLOC = _ROOT / "config" / "core_allocation.yaml"
_DEFAULT_OVERLAY = Path(
    os.getenv("ADMIN_RUNTIME_CONFIG", str(_ROOT / "data" / "admin_runtime_config.json"))
)


def _norm_exchange(raw: str) -> str:
    x = str(raw or "").strip().upper().replace(" ", "")
    if x in ("HSX", "HOSE"):
        return "HOSE"
    if x == "HNX":
        return "HNX"
    if x in ("UPCOM", "UPX") or x.startswith("UPCO"):
        return "UPCOM"
    return ""


def _read_admin_priceboard_overlay(overlay_path: Path | None = None) -> dict[str, Any]:
    path = overlay_path or _DEFAULT_OVERLAY
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    pb = doc.get("priceboard")
    return pb if isinstance(pb, dict) else {}


def load_allocation_config(path: Path | None = None) -> dict[str, Any]:
    p = path or Path(os.getenv("CORE_ALLOCATION_CONFIG", str(_DEFAULT_ALLOC)))
    doc: dict[str, Any] = {
        "max_core": 300,
        "lookback_sessions": 20,
        "allocation": {"HOSE": 160, "HNX": 80, "UPCOM": 60},
        "force_vn30": True,
        "listing_csv": "config/exchange_listing.csv",
        "ohlcv_dir": "data/ohlcv",
        "output": "config/priceboard_core_symbols.yaml",
    }
    if p.is_file():
        try:
            import yaml

            loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                doc.update(loaded)
        except Exception:
            pass
    # Admin-First overlay wins (sanitized)
    try:
        from backend.ops_config import sanitize_priceboard_ops

        pb_raw = _read_admin_priceboard_overlay()
        if pb_raw:
            safe, _ = sanitize_priceboard_ops(pb_raw)
            if isinstance(safe.get("core_allocation"), dict):
                doc["allocation"] = dict(safe["core_allocation"])
            if safe.get("max_core") is not None:
                doc["max_core"] = int(safe["max_core"])
            if safe.get("lookback_sessions") is not None:
                doc["lookback_sessions"] = int(safe["lookback_sessions"])
            if "force_vn30" in safe:
                doc["force_vn30"] = bool(safe["force_vn30"])
    except Exception:
        pass
    return doc


def _resolve(root: Path, maybe: str | Path) -> Path:
    p = Path(maybe)
    return p if p.is_absolute() else (root / p)


def load_exchange_listing(csv_path: Path) -> dict[str, str]:
    """symbol → HOSE|HNX|UPCOM."""
    out: dict[str, str] = {}
    if not csv_path.is_file():
        return out
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sym = str(row.get("symbol") or "").strip().upper()
            ex = _norm_exchange(str(row.get("exchange") or ""))
            if not sym or ex not in ("HOSE", "HNX", "UPCOM"):
                continue
            if not sym.isalnum() or len(sym) > 5:
                continue
            out[sym] = ex
    return out


def apply_catalog_overlay_exchanges(listing: dict[str, str], root: Path) -> dict[str, str]:
    """Prefer ``config/market_catalog.json`` exchange overrides when present."""
    path = root / "config" / "market_catalog.json"
    if not path.is_file():
        return listing
    try:
        import json

        doc = json.loads(path.read_text(encoding="utf-8")) or {}
        items = doc.get("items") if isinstance(doc, dict) else None
        if not isinstance(items, list):
            return listing
        out = dict(listing)
        for raw in items:
            if not isinstance(raw, dict):
                continue
            sym = str(raw.get("symbol") or "").strip().upper()
            ex = _norm_exchange(str(raw.get("exchange") or ""))
            if sym and ex in ("HOSE", "HNX", "UPCOM"):
                out[sym] = ex
        return out
    except Exception:
        return listing


def load_listing_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not csv_path.is_file():
        return rows
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sym = str(row.get("symbol") or "").strip().upper()
            ex = _norm_exchange(str(row.get("exchange") or ""))
            if not sym or ex not in ("HOSE", "HNX", "UPCOM"):
                continue
            rows.append(
                {
                    "symbol": sym,
                    "exchange": ex,
                    "name": str(row.get("name") or "").strip(),
                }
            )
    return rows


def score_ohlcv_liquidity(ohlcv_dir: Path, *, lookback: int = 20) -> dict[str, float]:
    """Average close*volume over last ``lookback`` sessions per symbol CSV."""
    scores: dict[str, float] = {}
    if not ohlcv_dir.is_dir():
        return scores
    lookback = max(1, int(lookback or 20))
    for path in ohlcv_dir.glob("*.csv"):
        sym = path.stem.strip().upper()
        if not sym:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        if len(lines) < 2:
            continue
        vals: list[float] = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            try:
                close = float(parts[4])
                vol = float(parts[5])
            except Exception:
                continue
            vals.append(close * vol)
        if not vals:
            continue
        window = vals[-lookback:]
        scores[sym] = sum(window) / len(window)
    return scores


def select_core_symbols(
    *,
    listing: dict[str, str],
    scores: dict[str, float],
    allocation: dict[str, int],
    force_vn30: bool = True,
) -> dict[str, list[str]]:
    """Return ordered picks per exchange."""
    quotas = {
        "HOSE": int(allocation.get("HOSE", 120)),
        "HNX": int(allocation.get("HNX", 60)),
        "UPCOM": int(allocation.get("UPCOM", 60)),
    }
    by_ex: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sym, ex in listing.items():
        by_ex[ex].append((sym, float(scores.get(sym, 0.0))))
    for ex in by_ex:
        by_ex[ex].sort(key=lambda t: (-t[1], t[0]))

    picked: dict[str, list[str]] = {"HOSE": [], "HNX": [], "UPCOM": []}
    seen: set[str] = set()

    if force_vn30:
        for sym in VN30_SYMBOLS:
            if listing.get(sym) == "HOSE" and sym not in seen:
                picked["HOSE"].append(sym)
                seen.add(sym)

    for ex, quota in quotas.items():
        for sym, _score in by_ex.get(ex, []):
            if sym in seen:
                continue
            picked[ex].append(sym)
            seen.add(sym)
            if len(picked[ex]) >= quota:
                break
    return picked


def flatten_core(picked: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for ex in ("HOSE", "HNX", "UPCOM"):
        out.extend(picked.get(ex) or [])
    return out


def render_core_yaml(
    symbols: list[str],
    *,
    picked: dict[str, list[str]],
    max_core: int = 240,
    lookback: int = 20,
) -> str:
    today = date.today().isoformat()
    lines = [
        "# Core stream — Top 240 cân sàn (liquidity-ranked).",
        f"# Allocation: HOSE {len(picked.get('HOSE') or [])} · "
        f"HNX {len(picked.get('HNX') or [])} · "
        f"UPCOM {len(picked.get('UPCOM') or [])}.",
        "# HOSE includes full VN30; remaining seats by avg(close*volume) OHLCV.",
        f"# Regenerated {today}. lookback_sessions={lookback}. Soft cap {max_core}.",
        "version: 1",
        f"max_core: {int(max_core)}",
        "allocation:",
        f"  HOSE: {len(picked.get('HOSE') or [])}",
        f"  HNX: {len(picked.get('HNX') or [])}",
        f"  UPCOM: {len(picked.get('UPCOM') or [])}",
        "symbols:",
    ]
    for sym in symbols[: int(max_core)]:
        lines.append(f"  - {sym}")
    lines.append("")
    return "\n".join(lines)


def build_core_symbols(*, root: Path | None = None, alloc_path: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    cfg = load_allocation_config(alloc_path)
    listing_path = _resolve(root, cfg.get("listing_csv") or "config/exchange_listing.csv")
    ohlcv_dir = _resolve(root, cfg.get("ohlcv_dir") or "data/ohlcv")
    output = _resolve(root, cfg.get("output") or "config/priceboard_core_symbols.yaml")
    lookback = int(cfg.get("lookback_sessions") or 20)
    max_core = int(cfg.get("max_core") or 240)
    allocation = dict(cfg.get("allocation") or {})
    force_vn30 = bool(cfg.get("force_vn30", True))

    listing = apply_catalog_overlay_exchanges(load_exchange_listing(listing_path), root)
    scores = score_ohlcv_liquidity(ohlcv_dir, lookback=lookback)
    picked = select_core_symbols(
        listing=listing,
        scores=scores,
        allocation=allocation,
        force_vn30=force_vn30,
    )
    symbols = flatten_core(picked)[:max_core]
    text = render_core_yaml(
        symbols,
        picked=picked,
        max_core=max_core,
        lookback=lookback,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "output": str(output),
        "count": len(symbols),
        "allocation": {ex: len(picked.get(ex) or []) for ex in ("HOSE", "HNX", "UPCOM")},
        "listing_size": len(listing),
        "scored": len(scores),
        "vn30_in_hose": sum(1 for s in VN30_SYMBOLS if s in (picked.get("HOSE") or [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate priceboard_core_symbols.yaml (120/60/60)")
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_ALLOC),
        help="Path to core_allocation.yaml",
    )
    parser.add_argument(
        "--root",
        default=str(_ROOT),
        help="Repo root (default: atz-desk root)",
    )
    args = parser.parse_args(argv)
    result = build_core_symbols(root=Path(args.root), alloc_path=Path(args.config))
    print(
        f"wrote {result['output']} count={result['count']} "
        f"alloc={result['allocation']} vn30={result['vn30_in_hose']}"
    )
    return 0 if result.get("ok") and result.get("count") == 240 else 1


if __name__ == "__main__":
    raise SystemExit(main())
