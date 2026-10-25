"""Seed / refresh OHLCV daily bars for iBoard «Tín hiệu ngày».

Chạy trên **host** (repo root + venv có ``vnstock``), không trong container ``api``
(``data/ohlcv`` mount read-only). Dùng loader legacy ``src/atz/datasource/client.load_bars``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from backend.board_universe import symbols_for_market_tab

MARKET_TABS = ("HOSE", "VN30", "HNX", "UPCOM")


def _legacy_atz_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "atz"


def _ensure_legacy_path() -> None:
    pkg = str(_legacy_atz_dir())
    if pkg not in sys.path:
        sys.path.insert(0, pkg)


def parse_markets(raw: str) -> list[str]:
    token = str(raw or "ALL").strip().upper()
    if token == "ALL":
        return list(MARKET_TABS)
    if token not in MARKET_TABS:
        raise ValueError(f"market must be one of {MARKET_TABS + ('ALL',)}, got {token!r}")
    return [token]


def collect_symbols(markets: list[str]) -> list[str]:
    """Union mã equity theo tab iBoard (không index/HĐTL)."""
    seen: set[str] = set()
    out: list[str] = []
    for tab in markets:
        for sym in symbols_for_market_tab(tab):
            code = str(sym).strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(code)
    return sorted(out)


@dataclass
class SeedRow:
    symbol: str
    ok: bool
    skipped: bool = False
    error: str = ""


def seed_symbols(
    symbols: list[str],
    *,
    start: str | None = None,
    sleep_seconds: float = 0.35,
    dry_run: bool = False,
) -> list[SeedRow]:
    if not symbols:
        return []
    if dry_run:
        return [SeedRow(symbol=s, ok=True, skipped=True) for s in symbols]

    _ensure_legacy_path()
    from config import CHART_DAYS  # noqa: PLC0415
    from datasource.client import load_bars  # noqa: PLC0415

    start_day = start or (date.today() - timedelta(days=int(CHART_DAYS))).isoformat()
    rows: list[SeedRow] = []
    for idx, sym in enumerate(symbols):
        try:
            frame = load_bars(sym, start_day)
            if frame is None:
                ok = False
            elif hasattr(frame, "empty"):
                ok = not bool(frame.empty)
            else:
                ok = True
            rows.append(SeedRow(symbol=sym, ok=ok))
        except Exception as exc:  # noqa: BLE001
            rows.append(SeedRow(symbol=sym, ok=False, error=str(exc)[:240]))
        if sleep_seconds > 0 and idx + 1 < len(symbols):
            time.sleep(sleep_seconds)
    return rows


def summarize(rows: list[SeedRow]) -> dict[str, int | bool]:
    dry = bool(rows) and all(r.skipped for r in rows)
    ok = sum(1 for r in rows if r.ok)
    fail = sum(1 for r in rows if not r.ok and not r.skipped)
    return {"total": len(rows), "ok": ok, "fail": fail, "dry_run": dry}


def bars_dir() -> Path:
    _ensure_legacy_path()
    from config import BARS_DIR  # noqa: PLC0415

    return Path(BARS_DIR)


def count_cached_symbols(symbols: list[str], root: Path | None = None) -> int:
    base = root or bars_dir()
    return sum(1 for s in symbols if (base / f"{s}.csv").is_file())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Seed data/ohlcv cho iBoard daily-signals (host VPS, cần vnstock trong venv).",
    )
    p.add_argument(
        "--market",
        default="ALL",
        help="HOSE | VN30 | HNX | UPCOM | ALL (default ALL = HOSE+HNX+UPCOM union)",
    )
    p.add_argument("--start", default=None, help="ISO start date (default CHART_DAYS từ legacy config).")
    p.add_argument("--sleep", type=float, default=0.35, help="Giây nghỉ giữa các mã (rate limit vnstock).")
    p.add_argument("--limit", type=int, default=0, help="Chỉ seed N mã đầu (0 = hết).")
    p.add_argument("--dry-run", action="store_true", help="Chỉ in danh sách mã, không gọi API.")
    p.add_argument("--json", action="store_true", help="In kết quả JSON (summary + rows).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        markets = parse_markets(args.market)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    symbols = collect_symbols(markets)
    if args.limit and args.limit > 0:
        symbols = symbols[: args.limit]

    before = count_cached_symbols(symbols)
    rows = seed_symbols(
        symbols,
        start=args.start,
        sleep_seconds=max(0.0, float(args.sleep)),
        dry_run=bool(args.dry_run),
    )
    after = count_cached_symbols(symbols)
    summary = summarize(rows)
    summary["markets"] = markets
    summary["cached_before"] = before
    summary["cached_after"] = after

    if args.json:
        payload = {"summary": summary, "rows": [asdict(r) for r in rows]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"markets={markets} symbols={summary['total']} "
            f"ok={summary['ok']} fail={summary['fail']} dry_run={summary['dry_run']}"
        )
        print(f"csv cached: {before} -> {after} / {summary['total']}")
        for row in rows:
            if row.skipped:
                continue
            if not row.ok:
                print(f"  FAIL {row.symbol}: {row.error or 'empty frame'}")

    fail = int(summary["fail"])
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
