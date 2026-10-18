#!/usr/bin/env python3
"""Chạy lọc universe theo theme; dùng chung cho daily/weekly."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    dbg,
    load_industry_map,
    load_themes,
    load_universe_config,
    resolve,
    utc_now,
    write_json,
)
from score import run_all_themes  # noqa: E402


def run(mode: str, cfg_path: Path | None = None) -> Path:
    cfg = load_universe_config(cfg_path)
    themes = load_themes(cfg.themes_path)
    industry = load_industry_map(cfg.industry_path)
    tables, metrics = run_all_themes(themes, industry, cfg)

    day = utc_now()[:10].replace("-", "")
    out = cfg.output_dir / day / mode
    out.mkdir(parents=True, exist_ok=True)
    by_theme = out / "by_theme"
    by_theme.mkdir(exist_ok=True)

    rows = []
    for theme in themes:
        table = tables[theme.key]
        table.to_csv(by_theme / f"{theme.key}.csv", index=False)
        rows.append(table)

    all_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    all_df.to_csv(out / "universe_all.csv", index=False)

    usable = [m for m in metrics if m.get("seed_with_bars", 0) > 0]
    missing = [m["theme"] for m in metrics if m.get("seed_with_bars", 0) <= 0]
    macro_recall = sum(m["recall"] for m in usable) / len(usable) if usable else 0.0
    macro_prec = sum(m["precision"] for m in usable) / len(usable) if usable else 0.0
    summary = {
        "mode": mode,
        "generated_at": utc_now(),
        "params": cfg.params,
        "macro_recall": round(macro_recall, 4),
        "macro_precision": round(macro_prec, 4),
        "themes_scored": len(usable),
        "themes_missing_bars": missing,
        "themes": metrics,
        "bars_dir": str(cfg.bars_dir),
        "output": str(out),
    }
    write_json(out / "summary.json", summary)

    lines = [
        f"# Sector universe ({mode})",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- macro_recall vs F3 seed (chỉ theme đã có bars): **{macro_recall:.1%}** "
        f"({len(usable)}/{len(metrics)} theme)",
        f"- macro_precision: **{macro_prec:.1%}**",
        f"- themes thiếu bars seed: `{', '.join(missing) or '—'}`",
        f"- min_vol20: `{cfg.params.get('min_vol20')}`",
        f"- k_ratio: `{cfg.params.get('k_ratio')}`",
        "",
        "| Theme | Recall | Precision | Selected | Seed có bars | Hit |",
        "|-------|--------|-----------|----------|--------------|-----|",
    ]
    for metric in metrics:
        lines.append(
            f"| {metric['theme']} | {metric['recall']:.1%} | {metric['precision']:.1%} | "
            f"{int(metric['selected_n'])} | {int(metric['seed_with_bars'])} | {int(metric['hit'])} |"
        )
    lines.append("")
    lines.append("Chi tiết CSV: `by_theme/*.csv`, `universe_all.csv`.")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Diff vs previous day (same mode) nếu có.
    prev_candidates = sorted(
        [p for p in cfg.output_dir.glob(f"*/{mode}/universe_all.csv") if p.parent.parent.name != day],
        reverse=True,
    )
    if prev_candidates and not all_df.empty:
        prev = pd.read_csv(prev_candidates[0])
        prev_set = set(prev["symbol"].astype(str).str.upper()) if "symbol" in prev.columns else set()
        cur_set = set(all_df["symbol"].astype(str).str.upper())
        entered = sorted(cur_set - prev_set)
        exited = sorted(prev_set - cur_set)
        diff_lines = [
            f"# Diff vs {prev_candidates[0].parent.parent.name}/{mode}",
            "",
            f"- entered ({len(entered)}): {', '.join(entered) or '—'}",
            f"- exited ({len(exited)}): {', '.join(exited) or '—'}",
            "",
        ]
        (out / "diff_vs_previous.md").write_text("\n".join(diff_lines), encoding="utf-8")

    dbg(f"{mode} done out={out} recall={macro_recall:.3f} prec={macro_prec:.3f}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "weekly", "adhoc"], default="adhoc")
    parser.add_argument("--config", type=Path, default=resolve("config/sector_universe.yaml"))
    args = parser.parse_args(argv)
    run(args.mode, args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
