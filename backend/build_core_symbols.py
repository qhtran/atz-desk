"""Sinh danh sách core từ CSV ứng viên (symbol,exchange,adtv VNĐ).

Không ghi ``config/priceboard_core_symbols.yaml`` khi file vào rỗng hoặc khi
một sàn không đủ mã sau cổng ADTV (tránh thay curated list bằng danh sách cụt).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from backend.admin_config_store import effective_liquidity_config
from backend.core_selector import (
    DEFAULT_QUOTAS,
    cache_core_symbols,
    select_core,
)


def load_candidates(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            if not raw:
                continue
            symbol = raw.get("symbol") or raw.get("Symbol") or raw.get("Mã") or ""
            exchange = raw.get("exchange") or raw.get("Exchange") or raw.get("sàn") or ""
            adtv = raw.get("adtv") or raw.get("ADTV") or raw.get("gtgd") or ""
            rows.append({"symbol": symbol, "exchange": exchange, "adtv": adtv})
    return rows


def _short_exchanges(selected: list[dict[str, Any]], quotas: dict[str, int]) -> list[str]:
    counts = {ex: 0 for ex in quotas}
    for row in selected:
        ex = str(row["exchange"])
        if ex in counts:
            counts[ex] += 1
    return [ex for ex, cap in quotas.items() if counts.get(ex, 0) < cap]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sinh core 300 sau bộ lọc ADTV.")
    parser.add_argument("--input", required=True, help="CSV symbol,exchange,adtv (adtv = VNĐ).")
    parser.add_argument(
        "--write-yaml",
        type=Path,
        default=None,
        help="Đường dẫn YAML core. Bỏ qua thì chỉ in số mã.",
    )
    parser.add_argument("--allow-short", action="store_true", help="Cho phép ghi khi một sàn chưa đủ quota.")
    parser.add_argument("--redis-url", default="", help="Ghi cache priceboard:core:symbols nếu set.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.input)
    if not path.is_file():
        print(f"missing input: {path}", file=sys.stderr)
        return 2
    rows = load_candidates(path)
    if not rows:
        print("input has no candidates; core yaml not modified", file=sys.stderr)
        return 2

    thresholds = effective_liquidity_config()
    selected = select_core(rows, min_traded_value=thresholds, quotas=DEFAULT_QUOTAS)
    short = _short_exchanges(selected, DEFAULT_QUOTAS)
    summary = {
        "input": len(rows),
        "selected": len(selected),
        "short": short,
        "min_traded_value": thresholds,
    }
    print(summary)

    if args.redis_url:
        import redis

        client = redis.Redis.from_url(args.redis_url, decode_responses=True, socket_connect_timeout=2)
        cache_core_symbols(client, selected, min_traded_value=thresholds, quotas=DEFAULT_QUOTAS)
        cached = client.get("priceboard:core:symbols")
        print({"redis": "priceboard:core:symbols", "bytes": len(cached or "")})

    if args.write_yaml is None:
        return 0
    if short and not args.allow_short:
        print(f"refusing to write short core: {short}", file=sys.stderr)
        return 3
    from backend.core_selector import render_core_yaml

    text = render_core_yaml(selected, min_traded_value=thresholds, quotas=DEFAULT_QUOTAS)
    args.write_yaml.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
