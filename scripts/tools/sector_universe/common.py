"""Shared helpers for sector_universe tool (branch feat/sector-universe-f3)."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


def dbg(msg: str) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    print(f"[DBG-{stamp}-SECTOR-UNI] {msg}", flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML không phải mapping: {path}")
    return data


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    return re.sub(r"[^\w\-]+", "", text, flags=re.UNICODE) or "theme"


@dataclass
class ThemeSpec:
    key: str
    label: str
    symbols: list[str]
    icb_names: list[str] = field(default_factory=list)
    whitelist: list[str] = field(default_factory=list)


@dataclass
class UniverseConfig:
    raw: dict[str, Any]
    themes_path: Path
    industry_path: Path
    bars_dir: Path
    output_dir: Path
    volume_window: int
    min_bars: int
    atr_window: int
    params: dict[str, Any]
    fit_grid: dict[str, Any]
    fit_objective: dict[str, float]
    pull: dict[str, Any]


def load_universe_config(path: Path | None = None) -> UniverseConfig:
    cfg_path = path or resolve("config/sector_universe.yaml")
    raw = load_yaml(cfg_path)
    paths = raw.get("paths") or {}
    features = raw.get("features") or {}
    defaults = dict(raw.get("defaults") or {})
    fitted = dict(raw.get("fitted") or {})
    # Fitted values override defaults when present and not null.
    params = {**defaults}
    for key, value in fitted.items():
        if key in {"fitted_at", "metrics"}:
            continue
        if value is not None:
            params[key] = value
    return UniverseConfig(
        raw=raw,
        themes_path=resolve(paths.get("themes", "config/sector_themes_f3.yaml")),
        industry_path=resolve(paths.get("industry", "data/industry_l3.csv")),
        bars_dir=resolve(paths.get("bars_dir", "data/sector_universe/ohlcv")),
        output_dir=resolve(paths.get("output_dir", "data/sector_universe/out")),
        volume_window=int(features.get("volume_window", 20)),
        min_bars=int(features.get("min_bars", 25)),
        atr_window=int(features.get("atr_window", 14)),
        params=params,
        fit_grid=dict(raw.get("fit_grid") or {}),
        fit_objective={
            "recall_weight": float((raw.get("fit_objective") or {}).get("recall_weight", 0.7)),
            "precision_weight": float((raw.get("fit_objective") or {}).get("precision_weight", 0.3)),
        },
        pull=dict(raw.get("pull") or {}),
    )


def load_themes(path: Path) -> list[ThemeSpec]:
    raw = load_yaml(path)
    themes = raw.get("themes") or {}
    result: list[ThemeSpec] = []
    for key, item in themes.items():
        if not isinstance(item, dict):
            continue
        symbols = [str(s).strip().upper() for s in (item.get("symbols") or []) if str(s).strip()]
        # unique keep order
        seen: set[str] = set()
        unique: list[str] = []
        for symbol in symbols:
            if symbol not in seen:
                seen.add(symbol)
                unique.append(symbol)
        result.append(
            ThemeSpec(
                key=str(key),
                label=str(item.get("label") or key),
                symbols=unique,
                icb_names=[str(x) for x in (item.get("icb_names") or [])],
                whitelist=[str(s).strip().upper() for s in (item.get("whitelist") or []) if str(s).strip()],
            )
        )
    return result


def load_industry_map(path: Path) -> dict[str, str]:
    import pandas as pd

    if not path.exists():
        return {}
    table = pd.read_csv(path)
    if "symbol" not in table.columns or "icb_name" not in table.columns:
        return {}
    symbols = table["symbol"].astype(str).str.upper()
    names = table["icb_name"].astype(str)
    return {
        symbol: name
        for symbol, name in zip(symbols, names)
        if symbol and name and name != "nan" and " " not in symbol and len(symbol) <= 4
    }


def candidate_symbols(
    theme: ThemeSpec,
    industry: dict[str, str],
    *,
    exclude: set[str] | None = None,
) -> list[str]:
    """Seed ∪ whitelist ∪ mã ICB thuộc theme, trừ mã đã thuộc seed theme khác."""
    allowed = set(theme.icb_names)
    blocked = set(exclude or ())
    # Không block chính seed/whitelist của theme này.
    blocked -= set(theme.symbols) | set(theme.whitelist)
    pool: list[str] = []
    seen: set[str] = set()

    def add(symbol: str) -> None:
        code = symbol.strip().upper()
        if not code or code in seen or code in blocked:
            return
        seen.add(code)
        pool.append(code)

    for symbol in theme.symbols:
        add(symbol)
    for symbol in theme.whitelist:
        add(symbol)
    if allowed:
        for symbol, icb in industry.items():
            if icb in allowed:
                add(symbol)
    return pool


def seeds_except(themes: list[ThemeSpec], current: ThemeSpec) -> set[str]:
    other: set[str] = set()
    for theme in themes:
        if theme.key == current.key:
            continue
        other.update(theme.symbols)
    return other


def top_k_for_theme(seed_n: int, params: dict[str, Any]) -> int:
    ratio = float(params.get("k_ratio", 1.0))
    k_min = int(params.get("k_min", 5))
    k_max = int(params.get("k_max", 22))
    raw = int(round(max(seed_n, 1) * ratio))
    return max(k_min, min(k_max, raw))


def safe_log1p(value: float) -> float:
    if value is None or (isinstance(value, float) and (math.isnan(value) or value < 0)):
        return 0.0
    return math.log1p(float(value))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
