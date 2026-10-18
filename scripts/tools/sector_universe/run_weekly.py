#!/usr/bin/env python3
"""Job hàng tuần: pull peers (tuỳ chọn) + fit lại nhẹ + xuất universe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import dbg, resolve  # noqa: E402
from run_filter import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sector universe weekly job")
    parser.add_argument("--config", type=Path, default=resolve("config/sector_universe.yaml"))
    parser.add_argument("--pull-peers", action="store_true", help="Pull seed + ICB peers")
    parser.add_argument("--refit", action="store_true", help="Grid-fit lại và ghi config")
    args = parser.parse_args(argv)

    if args.pull_peers:
        from pull_bars import main as pull_main

        code = pull_main(["--config", str(args.config), "--with-peers"])
        if code != 0:
            dbg("WARN pull peers có lỗi — vẫn chạy filter trên bars sẵn có")

    if args.refit:
        from fit import fit_params, write_fitted

        result = fit_params(args.config)
        write_fitted(args.config, result)
        dbg(
            f"refit objective={result['score']:.4f} recall={result['recall']:.3f} "
            f"precision={result['precision']:.3f}"
        )

    run("weekly", args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
