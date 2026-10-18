#!/usr/bin/env python3
"""Kéo OHLCV vào data/sector_universe/ohlcv (cache riêng, không đụng data/ohlcv app)."""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from datetime import date, timedelta
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
)


def _symbols_needed(cfg) -> list[str]:
    themes = load_themes(cfg.themes_path)
    industry = load_industry_map(cfg.industry_path)
    # Phase 0 ưu tiên seed+whitelist; ICB peers kéo thêm nếu --with-peers.
    return sorted({s for t in themes for s in (t.symbols + t.whitelist)})


def _symbols_with_peers(cfg) -> list[str]:
    themes = load_themes(cfg.themes_path)
    industry = load_industry_map(cfg.industry_path)
    pool: set[str] = set()
    for theme in themes:
        pool.update(candidate_symbols(theme, industry, exclude=seeds_except(themes, theme)))
    return sorted(pool)


def _fresh(path: Path, skip_fresh_days: int) -> bool:
    if not path.exists():
        return False
    age_days = (date.today() - date.fromtimestamp(path.stat().st_mtime)).days
    return age_days <= skip_fresh_days


def pull_one(symbol: str, start: str, end: str, dest: Path) -> tuple[bool, str]:
    try:
        from vnstock import Market
    except ImportError as error:
        return False, f"vnstock chưa cài: {error}"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            frame = Market().equity(symbol).ohlcv(
                start=start,
                end=end,
                interval="1D",
                source="kbs",
            )
        if frame is None or getattr(frame, "empty", True):
            return False, "empty"
        dest.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(dest, index=False)
        return True, f"rows={len(frame)}"
    except Exception as error:  # noqa: BLE001
        text = str(error).replace("\n", " ")
        if "5.0.1" in text or "cập nhật lên bản" in text.lower():
            text = "vnstock bị tắt/cũ — cần nâng lên >=5.1.0 rồi pull lại"
        return False, text[:160]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull OHLCV cho sector universe")
    parser.add_argument("--config", type=Path, default=resolve("config/sector_universe.yaml"))
    parser.add_argument("--with-peers", action="store_true", help="Kéo cả mã ICB peer, không chỉ seed")
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số mã (test)")
    parser.add_argument("--force", action="store_true", help="Bỏ qua skip_fresh")
    args = parser.parse_args(argv)

    cfg = load_universe_config(args.config)
    pull = cfg.pull
    lookback = int(pull.get("lookback_days", 230))
    sleep_s = float(pull.get("sleep_seconds", 0.15))
    skip_fresh = int(pull.get("skip_fresh_days", 3))
    max_symbols = int(args.limit or pull.get("max_symbols") or 0)

    symbols = _symbols_with_peers(cfg) if args.with_peers else _symbols_needed(cfg)
    if max_symbols > 0:
        symbols = symbols[:max_symbols]

    start = (date.today() - timedelta(days=lookback)).isoformat()
    end = date.today().isoformat()
    dbg(f"pull symbols={len(symbols)} start={start} dest={cfg.bars_dir} peers={args.with_peers}")

    ok = fail = skip = 0
    for index, symbol in enumerate(symbols, start=1):
        dest = cfg.bars_dir / f"{symbol}.csv"
        if not args.force and _fresh(dest, skip_fresh):
            skip += 1
            continue
        success, detail = pull_one(symbol, start, end, dest)
        if success:
            ok += 1
            dbg(f"[{index}/{len(symbols)}] OK {symbol} {detail}")
        else:
            fail += 1
            dbg(f"[{index}/{len(symbols)}] FAIL {symbol} {detail}")
        if sleep_s > 0:
            time.sleep(sleep_s)

    dbg(f"DONE ok={ok} fail={fail} skip={skip}")
    return 0 if fail == 0 or ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
