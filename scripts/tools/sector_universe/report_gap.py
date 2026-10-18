#!/usr/bin/env python3
"""Báo cáo gap mentor F3 vs output model (S-020)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    candidate_symbols,
    dbg,
    load_industry_map,
    load_themes,
    load_universe_config,
    resolve,
    seeds_except,
    utc_now,
    write_json,
)
from features import load_bars  # noqa: E402
from score import run_all_themes  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gap report F3 mentor vs model")
    parser.add_argument("--config", type=Path, default=resolve("config/sector_universe.yaml"))
    parser.add_argument(
        "--out",
        type=Path,
        default=resolve("docs/specs/F3_SECTOR_UNIVERSE.md"),
        help="Markdown report path",
    )
    args = parser.parse_args(argv)

    cfg = load_universe_config(args.config)
    themes = load_themes(cfg.themes_path)
    industry = load_industry_map(cfg.industry_path)
    tables, metrics = run_all_themes(themes, industry, cfg)

    seed_all: set[str] = set()
    for theme in themes:
        seed_all.update(theme.symbols)

    bars_ok: list[str] = []
    for symbol in sorted(seed_all):
        frame = load_bars(cfg.bars_dir, symbol)
        if frame is not None and len(frame) >= cfg.min_bars:
            bars_ok.append(symbol)
    bars_missing = sorted(seed_all - set(bars_ok))

    rows = []
    miss_seed_total: list[str] = []
    false_pos_total: list[str] = []
    for theme, metric in zip(themes, metrics):
        selected = set(tables[theme.key]["symbol"].astype(str).str.upper()) if not tables[theme.key].empty else set()
        seed = set(theme.symbols)
        seed_bars = {s for s in seed if s in bars_ok}
        miss = sorted(seed_bars - selected)  # mentor có bars nhưng model bỏ
        false_pos = sorted(selected - seed)
        miss_seed_total.extend(f"{theme.key}:{s}" for s in miss)
        false_pos_total.extend(f"{theme.key}:{s}" for s in false_pos)
        cands = candidate_symbols(theme, industry, exclude=seeds_except(themes, theme))
        rows.append(
            {
                "theme": theme.key,
                "label": theme.label,
                "seed_n": len(seed),
                "seed_with_bars": int(metric["seed_with_bars"]),
                "selected_n": int(metric["selected_n"]),
                "recall": metric["recall"],
                "precision": metric["precision"],
                "hit": int(metric["hit"]),
                "candidates": len(cands),
                "miss_seed_with_bars": miss,
                "false_positive": false_pos[:12],
            }
        )

    usable = [r for r in rows if r["seed_with_bars"] > 0]
    macro_r = sum(r["recall"] for r in usable) / len(usable) if usable else 0.0
    macro_p = sum(r["precision"] for r in usable) / len(usable) if usable else 0.0
    params = cfg.params

    lines = [
        "# F3 Sector Universe — reverse-fit & gap report (S-020)",
        "",
        f"**Status:** Spec Ready (chờ Master ack)  ",
        f"**Owner:** ag3 / sp1  ",
        f"**Generated:** `{utc_now()}`  ",
        f"**Branch:** `feat/sector-universe-f3`  ",
        f"**Tool:** `scripts/tools/sector_universe/`  ",
        "",
        "## 1. Mục tiêu",
        "",
        "Document độ gần model lọc thematic so với seed mentor F3: recall / precision / gap.",
        "Không đổi UI T-230; không deploy; Phase 2 correlation = future.",
        "",
        "## 2. Fitted params (đang dùng)",
        "",
        "Nguồn: khối `fitted` trong `config/sector_universe.yaml` (sau `fit.py --write-config`).",
        "",
        "| Param | Value |",
        "|-------|-------|",
        f"| `w_log_gtgd` | `{params.get('w_log_gtgd')}` |",
        f"| `w_log_vol` | `{params.get('w_log_vol')}` |",
        f"| `w_atr` | `{params.get('w_atr')}` |",
        f"| `min_vol20` | `{params.get('min_vol20')}` |",
        f"| `k_ratio` | `{params.get('k_ratio')}` |",
        f"| `k_min` / `k_max` | `{params.get('k_min')}` / `{params.get('k_max')}` |",
        f"| `keep_seed_if_listed` | `{params.get('keep_seed_if_listed')}` |",
        f"| `keep_whitelist` | `{params.get('keep_whitelist')}` |",
        "",
        "Score: `w_gtgd·z(log GTGD20) + w_vol·z(log VOL20) + w_atr·ATR_score` rồi top-K theo `k_ratio`.",
        "",
        "## 3. Coverage dữ liệu (ràng buộc chính)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Seed mentor (unique) | **{len(seed_all)}** |",
        f"| Seed có OHLCV đủ `min_bars` | **{len(bars_ok)}** |",
        f"| Seed thiếu bars | **{len(bars_missing)}** |",
        f"| Bars dir | `{cfg.bars_dir}` |",
        "",
        "**Lưu ý:** `vnstock==5.0.1` trên máy dev có thể bị tắt API → `pull_bars.py` fail.",
        "Recall bên dưới chỉ tính trên seed **đã có bars** (không phạt thiếu cache).",
        "Muốn số liệu đầy đủ: nâng `vnstock>=5.1.0` rồi `pull_bars.py` (+ optional `--with-peers`) + `fit.py --write-config`.",
        "",
        "### Seed thiếu bars (sample)",
        "",
        ", ".join(bars_missing[:40]) + (" …" if len(bars_missing) > 40 else ""),
        "",
        "## 4. Bảng tóm tắt theo theme",
        "",
        f"Macro (theme có bars): **recall={macro_r:.1%}** · **precision={macro_p:.1%}** · themes scored={len(usable)}/{len(rows)}",
        "",
        "| Theme | Seed | Có bars | Selected | Recall | Precision | Hit | Miss (seed+bars) | FP (sample) |",
        "|-------|-----:|--------:|---------:|-------:|----------:|----:|------------------|-------------|",
    ]
    for r in rows:
        miss = ", ".join(r["miss_seed_with_bars"]) or "—"
        fp = ", ".join(r["false_positive"]) or "—"
        lines.append(
            f"| {r['theme']} | {r['seed_n']} | {r['seed_with_bars']} | {r['selected_n']} | "
            f"{r['recall']:.0%} | {r['precision']:.0%} | {r['hit']} | {miss} | {fp} |"
        )

    lines += [
        "",
        "## 5. Gap analysis",
        "",
        "### 5.1 Mentor miss (có bars nhưng model không giữ)",
        "",
        f"- Count: **{len(miss_seed_total)}**",
        f"- List: {', '.join(miss_seed_total) or '—'}",
        "",
        "Với `keep_seed_if_listed=true`, miss chỉ xảy ra khi seed **không có bars** đủ hoặc bị loại khỏi top-K sau khi không pass vol và không keep — kiểm tra lại nếu count > 0 khi đủ data.",
        "",
        "### 5.2 False positive (model chọn ngoài seed)",
        "",
        f"- Count (theme-tagged): **{len(false_pos_total)}** (liệt kê mẫu trong bảng §4).",
        "- Thường là peer ICB thanh khoản cao lọt top-K — đúng hành vi “mở rộng thematic”, không nhất thiết lỗi.",
        "",
        "### 5.3 Theme 0 bars",
        "",
        ", ".join(r["theme"] for r in rows if r["seed_with_bars"] == 0) or "—",
        "",
        "## 6. Kết luận S-020",
        "",
        "1. Pipeline reverse-fit **chạy được** (fit/score/daily) trên cache hiện có.",
        "2. Trên subset có bars: recall cao nhờ `keep_seed_if_listed` — đây là gần mentor theo thiết kế Phase 1.",
        "3. **Blocker số liệu đầy đủ:** thiếu OHLCV ~"
        + str(len(bars_missing))
        + " mã seed → cần pull lại sau khi nâng vnstock.",
        "4. Future (không làm S-020): Phase 2 correlation cùng sóng; import UI catalog đã có qua T-230 seed loader.",
        "",
        "## 7. Lệnh tái tạo report",
        "",
        "```bash",
        ".venv/bin/python scripts/tools/sector_universe/fit.py --write-config",
        ".venv/bin/python scripts/tools/sector_universe/report_gap.py",
        ".venv/bin/python scripts/tools/sector_universe/run_daily.py",
        "```",
        "",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "generated_at": utc_now(),
        "macro_recall": macro_r,
        "macro_precision": macro_p,
        "seed_n": len(seed_all),
        "seed_with_bars": len(bars_ok),
        "seed_missing_bars": len(bars_missing),
        "miss_seed_with_bars": miss_seed_total,
        "false_positive_n": len(false_pos_total),
        "params": params,
        "themes": rows,
    }
    json_path = cfg.output_dir / "gap_report.json"
    write_json(json_path, summary)
    dbg(f"wrote {args.out}")
    dbg(f"wrote {json_path}")
    dbg(f"macro_recall={macro_r:.3f} macro_precision={macro_p:.3f} bars={len(bars_ok)}/{len(seed_all)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
