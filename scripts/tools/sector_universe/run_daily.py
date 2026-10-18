#!/usr/bin/env python3
"""Job hàng ngày: rescore thanh khoản + xuất universe theo theme."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import resolve  # noqa: E402
from run_filter import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sector universe daily job")
    parser.add_argument("--config", type=Path, default=resolve("config/sector_universe.yaml"))
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Kéo lại OHLCV seed trước khi lọc (chậm, cần mạng)",
    )
    args = parser.parse_args(argv)
    if args.pull:
        from pull_bars import main as pull_main

        code = pull_main(["--config", str(args.config)])
        if code != 0:
            return code
    run("daily", args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
