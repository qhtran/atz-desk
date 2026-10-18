#!/usr/bin/env python3
"""Grid-search tham số để gần seed F3 (maximize recall rồi precision)."""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path
from typing import Any

# Allow running as script from this folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    dbg,
    load_industry_map,
    load_themes,
    load_universe_config,
    load_yaml,
    resolve,
    save_yaml,
    utc_now,
)
from score import run_all_themes  # noqa: E402


def _grid(fit_grid: dict[str, Any]) -> list[dict[str, Any]]:
    keys = ["w_log_gtgd", "w_log_vol", "w_atr", "min_vol20", "k_ratio"]
    axes = []
    for key in keys:
        values = fit_grid.get(key)
        if not values:
            raise ValueError(f"fit_grid thiếu {key}")
        axes.append([(key, value) for value in values])
    combos = []
    for product in itertools.product(*axes):
        combos.append({key: value for key, value in product})
    return combos


def objective(metrics: list[dict[str, float]], weights: dict[str, float]) -> tuple[float, float, float]:
    if not metrics:
        return 0.0, 0.0, 0.0
    # Macro-average theo theme có seed_with_bars > 0; theme chưa pull không phạt nặng.
    usable = [m for m in metrics if m.get("seed_with_bars", 0) > 0]
    if not usable:
        usable = metrics
    recall = sum(m["recall"] for m in usable) / len(usable)
    precision = sum(m["precision"] for m in usable) / len(usable)
    score = weights["recall_weight"] * recall + weights["precision_weight"] * precision
    return score, recall, precision


def fit_params(cfg_path: Path | None = None) -> dict[str, Any]:
    cfg = load_universe_config(cfg_path)
    themes = load_themes(cfg.themes_path)
    industry = load_industry_map(cfg.industry_path)
    base = dict(cfg.params)
    best: dict[str, Any] | None = None
    best_score = -1.0
    best_metrics: list[dict[str, float]] = []
    combos = _grid(cfg.fit_grid)
    dbg(f"fit start combos={len(combos)} themes={len(themes)} bars_dir={cfg.bars_dir}")

    for index, combo in enumerate(combos, start=1):
        trial = {**base, **combo}
        _, metrics = run_all_themes(themes, industry, cfg, params=trial)
        score, recall, precision = objective(metrics, cfg.fit_objective)
        if score > best_score:
            best_score = score
            best = trial
            best_metrics = metrics
            dbg(
                f"new best #{index}/{len(combos)} score={score:.4f} "
                f"recall={recall:.3f} prec={precision:.3f} params={combo}"
            )

    assert best is not None
    per_theme = {
        m["theme"]: {
            "recall": round(m["recall"], 4),
            "precision": round(m["precision"], 4),
            "selected_n": int(m["selected_n"]),
            "seed_with_bars": int(m["seed_with_bars"]),
            "hit": int(m["hit"]),
        }
        for m in best_metrics
    }
    _, recall, precision = objective(best_metrics, cfg.fit_objective)
    return {
        "params": best,
        "score": best_score,
        "recall": recall,
        "precision": precision,
        "per_theme": per_theme,
        "fitted_at": utc_now(),
    }


def write_fitted(cfg_path: Path, result: dict[str, Any]) -> None:
    raw = load_yaml(cfg_path)
    params = result["params"]
    fitted = {
        "w_log_gtgd": float(params["w_log_gtgd"]),
        "w_log_vol": float(params["w_log_vol"]),
        "w_atr": float(params["w_atr"]),
        "min_vol20": float(params["min_vol20"]),
        "k_ratio": float(params["k_ratio"]),
        "k_min": int(params.get("k_min", 5)),
        "k_max": int(params.get("k_max", 22)),
        "keep_seed_if_listed": bool(params.get("keep_seed_if_listed", True)),
        "keep_whitelist": bool(params.get("keep_whitelist", True)),
        "fitted_at": result["fitted_at"],
        "metrics": {
            "objective": round(float(result["score"]), 4),
            "macro_recall": round(float(result["recall"]), 4),
            "macro_precision": round(float(result["precision"]), 4),
            "per_theme": result["per_theme"],
        },
    }
    raw["fitted"] = fitted
    save_yaml(cfg_path, raw)
    dbg(f"wrote fitted → {cfg_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit tham số sector universe gần F3")
    parser.add_argument(
        "--config",
        type=Path,
        default=resolve("config/sector_universe.yaml"),
        help="Đường dẫn config",
    )
    parser.add_argument(
        "--write-config",
        action="store_true",
        help="Ghi khối fitted vào config",
    )
    args = parser.parse_args(argv)
    result = fit_params(args.config)
    dbg(
        f"DONE objective={result['score']:.4f} recall={result['recall']:.3f} "
        f"precision={result['precision']:.3f}"
    )
    for theme, metric in result["per_theme"].items():
        dbg(f"  {theme}: {metric}")
    if args.write_config:
        write_fitted(args.config, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
