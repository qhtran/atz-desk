"""Morning brief engine + CLI (``python -m backend.morning_brief``).

Hybrid: curated watchbook (SQLite) + F3 technical appendix (BB/Ichimoku D/W/M).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from backend.f3_indicators import alert_column_for_bars, load_f3_alert_config
from backend.morning_brief_ai import enrich_watchbook_for_ai, maybe_gemini_rewrite
from backend.morning_brief_facts import build_session_facts, format_facts_macro_block
from backend.morning_brief_store import (
    STATUS_HOLD,
    STATUS_RESIST,
    STATUS_STOP,
    get_config,
    init_brief_store,
    list_watchbook,
    save_daily_brief,
    seed_watchbook_from_yaml,
    update_watch_status,
)
from backend.portfolio_f3 import load_f3_sector_themes, load_symbol_bars
from backend.portfolio_quotes import DEFAULT_BARS_DIR, ohlcv_last_close_vnd

logger = logging.getLogger("morning_brief")

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SEED = _ROOT / "config" / "morning_brief_watchbook.yaml"
TZ_NAME = "Asia/Ho_Chi_Minh"
DEFAULT_TITLE = "@All Kg các NĐT bản tin sáng ngày {date}"
AI_TITLE_SUFFIX = " [AI Assisted]"


def apply_ai_title_suffix(title: str) -> str:
    """Gắn hậu tố nhận diện Mode 2; idempotent."""
    base = str(title or "").rstrip()
    if not base:
        return AI_TITLE_SUFFIX.strip()
    if base.endswith(AI_TITLE_SUFFIX.strip()) or "[AI Assisted]" in base:
        return base
    return base + AI_TITLE_SUFFIX


def sync_body_title_line(body: str, title: str) -> str:
    """Đồng bộ dòng đầu markdown với title đã gắn nhãn AI (nếu có)."""
    text = str(body or "")
    if not text.strip():
        return str(title or "")
    lines = text.splitlines()
    first = lines[0].strip() if lines else ""
    if first.startswith("@All") or "[AI Assisted]" in first:
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    rest = "\n".join(lines).strip("\n")
    return str(title) + ("\n\n" + rest if rest else "")


def _vn_today() -> date:
    return datetime.now(ZoneInfo(TZ_NAME)).date()


def _format_vn_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def resample_ohlcv(frame: pd.DataFrame, rule: str) -> pd.DataFrame | None:
    """Resample daily OHLCV to W or ME. Requires a date-like column."""
    if frame is None or frame.empty:
        return None
    df = frame.copy()
    lookup = {str(c).lower(): c for c in df.columns}
    time_col = next((lookup[k] for k in ("time", "date", "trading_date") if k in lookup), None)
    if time_col is None:
        return None
    for need in ("open", "high", "low", "close"):
        if need not in lookup:
            return None
    df["_dt"] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=["_dt"]).sort_values("_dt")
    if df.empty:
        return None
    df = df.set_index("_dt")
    agg: dict[str, str] = {
        lookup["open"]: "first",
        lookup["high"]: "max",
        lookup["low"]: "min",
        lookup["close"]: "last",
    }
    if "volume" in lookup:
        agg[lookup["volume"]] = "sum"
    out = df.resample(rule).agg(agg).dropna(how="any")
    if out.empty:
        return None
    out = out.reset_index().rename(columns={"_dt": "time"})
    # Normalize column names to open/high/low/close/volume for F3
    rename = {
        lookup["open"]: "open",
        lookup["high"]: "high",
        lookup["low"]: "low",
        lookup["close"]: "close",
    }
    if "volume" in lookup:
        rename[lookup["volume"]] = "volume"
    out = out.rename(columns=rename)
    return out


def evaluate_watch_status(last: float | None, stop_loss: float | None, resistance: float | None) -> str:
    if last is None or not (last == last) or last <= 0:
        return STATUS_HOLD
    if stop_loss is not None and last <= float(stop_loss):
        return STATUS_STOP
    if resistance is not None and last >= float(resistance):
        return STATUS_RESIST
    return STATUS_HOLD


def refresh_watchbook_statuses(
    *,
    bars_dir: Path,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for item in list_watchbook(db_path=db_path):
        last = ohlcv_last_close_vnd(bars_dir, item["symbol"])
        new_status = evaluate_watch_status(last, item.get("stop_loss"), item.get("resistance"))
        if new_status != item.get("status"):
            row = update_watch_status(int(item["id"]), new_status, db_path=db_path)
            if row:
                updated.append(row)
        else:
            updated.append(item)
    return list_watchbook(db_path=db_path)


def _theme_leaders(theme_ids: list[str], limit_per: int = 3) -> list[tuple[str, str]]:
    """Return (theme_label, symbol) pairs for appendix / sector notes."""
    themes = load_f3_sector_themes()
    by_id = {}
    for t in themes:
        tid = str(t.get("id") or "").replace("f3:", "")
        by_id[tid] = t
        # also key without prefix if already clean
        by_id[str(t.get("id") or "")] = t
    out: list[tuple[str, str]] = []
    for tid in theme_ids:
        key = str(tid).strip()
        theme = by_id.get(key) or by_id.get(f"f3:{key}")
        if not theme:
            continue
        label = str(theme.get("name") or key)
        symbols = list(theme.get("symbols") or [])[:limit_per]
        for sym in symbols:
            out.append((label, str(sym).upper()))
    return out


def build_tech_appendix(
    symbols: list[str],
    *,
    bars_dir: Path,
    session_date: date | None = None,
) -> list[dict[str, Any]]:
    cfg = load_f3_alert_config()
    day = session_date or _vn_today()
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        bars = load_symbol_bars(sym, bars_dir)
        if bars is None:
            rows.append(
                {
                    "symbol": sym,
                    "D": "insufficient_data",
                    "W": "insufficient_data",
                    "M": "insufficient_data",
                }
            )
            continue
        daily = alert_column_for_bars(sym, bars, session_date=day, config=cfg)
        weekly_bars = resample_ohlcv(bars, "W-FRI")
        monthly_bars = resample_ohlcv(bars, "ME")
        weekly = (
            alert_column_for_bars(sym, weekly_bars, session_date=day, config=cfg)
            if weekly_bars is not None
            else "insufficient_data"
        )
        monthly = (
            alert_column_for_bars(sym, monthly_bars, session_date=day, config=cfg)
            if monthly_bars is not None
            else "insufficient_data"
        )
        rows.append({"symbol": sym, "D": daily, "W": weekly, "M": monthly})
    return rows


def _index_macro_line(bars_dir: Path, symbol: str = "VNINDEX") -> str:
    bars = load_symbol_bars(symbol, bars_dir)
    if bars is None or bars.empty:
        return f"{symbol}: thiếu OHLCV — không đủ dữ liệu nhận định."
    lookup = {str(c).lower(): c for c in bars.columns}
    if "close" not in lookup:
        return f"{symbol}: thiếu cột close."
    close = pd.to_numeric(bars[lookup["close"]], errors="coerce").dropna()
    if len(close) < 2:
        return f"{symbol}: không đủ phiên."
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg = (last - prev) / prev * 100 if prev else 0.0
    direction = "tăng" if chg > 0 else ("giảm" if chg < 0 else "đi ngang")
    phrase = alert_column_for_bars(symbol, bars)
    return (
        f"{symbol} đóng {last:.2f} ({direction} {chg:+.2f}% phiên trước). "
        f"Kỹ thuật ngày: {phrase}."
    )


def _sector_lines(theme_ids: list[str], bars_dir: Path) -> list[str]:
    lines: list[str] = []
    for label, sym in _theme_leaders(theme_ids, limit_per=1):
        phrase = alert_column_for_bars(sym, load_symbol_bars(sym, bars_dir))
        lines.append(f"- {label} (đại diện {sym}): {phrase}")
    return lines


def _cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _pct_cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _render_watchbook_table(enriched: list[dict[str, Any]]) -> list[str]:
    """Bảng Watchbook chuẩn Fireant/XO (Mode 1)."""
    lines = [
        "## Danh mục khuyến nghị (Watchbook chuẩn)",
        "",
        "| TT | Mã CP | Giá Hiện Tại | Ngày KN | GD T+ | Giá Mua | Giá Cắt Lỗ (5%) | "
        "Hỗ trợ kỹ thuật | Kháng cự KT (Mục tiêu giá) | LN Tạm Tính | (%) | Khuyến nghị |",
        "|---:|:---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in enriched:
        lines.append(
            "| {tt} | {sym} | {last} | {bd} | {tplus} | {bp} | {sl5} | {sup} | {res} | {pnl} | {pct} | {kn} |".format(
                tt=item.get("tt") or "",
                sym=item.get("symbol") or "",
                last=_cell(item.get("last_price")),
                bd=item.get("buy_date") or "—",
                tplus=item.get("gd_t_plus") or "—",
                bp=_cell(item.get("buy_price")),
                sl5=_cell(item.get("stop_loss_5pct")),
                sup=_cell(item.get("support_kt")),
                res=_cell(item.get("resistance_kt")),
                pnl=_cell(item.get("pnl")),
                pct=_pct_cell(item.get("pnl_pct")),
                kn=item.get("khuyen_nghi_goi_y") or "Giữ",
            )
        )
    lines.append("")
    return lines


def render_brief_markdown(
    *,
    brief_date: date,
    config: dict[str, Any],
    watchbook: list[dict[str, Any]],
    tech_rows: list[dict[str, Any]],
    macro_line: str,
    sector_lines: list[str],
    session_facts: dict[str, Any] | None = None,
    watchbook_enriched: list[dict[str, Any]] | None = None,
) -> tuple[str, str, dict[str, Any]]:
    date_label = _format_vn_date(brief_date)
    title_tpl = str(config.get("title_template") or DEFAULT_TITLE)
    title = title_tpl.format(date=date_label)

    facts = session_facts or {}
    parts: list[str] = [
        title,
        "",
        f"## Nhận định thị trường ngày {date_label}",
        "",
    ]
    if facts:
        parts.append(format_facts_macro_block(facts))
        parts.append("")
    else:
        parts.append(macro_line)
        parts.append("")

    override = str(config.get("macro_override") or "").strip()
    if override and override not in "\n".join(parts):
        # Tuỳ chọn: ghi chú admin — không thay số liệu auto.
        parts.append(f"> Ghi chú admin: {override}")
        parts.append("")

    if sector_lines:
        parts.append("### Nhóm ngành")
        parts.extend(sector_lines)
        parts.append("")

    enriched = watchbook_enriched
    if enriched is None:
        enriched = enrich_watchbook_for_ai(watchbook, tech_rows=tech_rows)
    parts.extend(_render_watchbook_table(enriched))

    parts.append("## Phụ lục tín hiệu kỹ thuật sáng (F3 · D/W/M)")
    parts.append("")
    parts.append("| Mã | Ngày (D) | Tuần (W) | Tháng (M) |")
    parts.append("|---|---|---|---|")
    for row in tech_rows:
        parts.append(
            f"| {row['symbol']} | {row['D']} | {row['W']} | {row['M']} |"
        )
    parts.append("")
    body = "\n".join(parts)
    body_json = {
        "brief_date": brief_date.isoformat(),
        "macro": macro_line,
        "session_facts": facts,
        "sectors": sector_lines,
        "watchbook": watchbook,
        "watchbook_enriched": enriched,
        "tech_appendix": tech_rows,
    }
    return title, body, body_json


def collect_tech_symbols(config: dict[str, Any], watchbook: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()

    def add(sym: str) -> None:
        s = str(sym or "").strip().upper()
        if not s or s in seen:
            return
        seen.add(s)
        symbols.append(s)

    for s in config.get("index_symbols") or ["VNINDEX"]:
        add(str(s))
    for _label, sym in _theme_leaders(list(config.get("sector_theme_ids") or []), limit_per=2):
        add(sym)
    for item in watchbook:
        add(str(item.get("symbol") or ""))
    for s in config.get("tech_symbols") or []:
        add(str(s))
    return symbols


def generate_morning_brief(
    *,
    brief_date: date | None = None,
    bars_dir: Path | None = None,
    db_path: Path | None = None,
    seed_yaml: Path | None = None,
) -> dict[str, Any]:
    """Generate + persist daily brief. Raises RuntimeError on hard OHLCV failure."""
    init_brief_store(db_path)
    seed = seed_yaml or Path(os.getenv("MORNING_BRIEF_SEED", str(_DEFAULT_SEED)))
    seed_watchbook_from_yaml(seed, db_path=db_path)

    day = brief_date or _vn_today()
    bars = bars_dir or DEFAULT_BARS_DIR
    config = get_config(db_path)
    if not config.get("enabled", True):
        raise RuntimeError("ERR-BRIEF-010: morning brief disabled in config")

    index_syms = list(config.get("index_symbols") or ["VNINDEX"])
    primary = str(index_syms[0] if index_syms else "VNINDEX").upper()
    if load_symbol_bars(primary, bars) is None:
        raise RuntimeError(f"ERR-BRIEF-011: missing OHLCV for {primary} under {bars}")

    watchbook = refresh_watchbook_statuses(bars_dir=bars, db_path=db_path)
    tech_symbols = collect_tech_symbols(config, watchbook)
    tech_rows = build_tech_appendix(tech_symbols, bars_dir=bars, session_date=day)
    sectors = _sector_lines(list(config.get("sector_theme_ids") or []), bars)

    index_tech = next(
        (row for row in tech_rows if str(row.get("symbol") or "").upper() == primary),
        None,
    )
    session_facts = build_session_facts(
        bars_dir=bars,
        index_symbol=primary,
        index_tech=index_tech,
    )
    # macro_line: luôn auto từ bars (không phụ thuộc Admin paste).
    macro = _index_macro_line(bars, primary)
    watchbook_enriched = enrich_watchbook_for_ai(
        watchbook,
        tech_rows=tech_rows,
        bars_dir=bars,
    )

    title, body, body_json = render_brief_markdown(
        brief_date=day,
        config=config,
        watchbook=watchbook,
        tech_rows=tech_rows,
        macro_line=macro,
        sector_lines=sectors,
        session_facts=session_facts,
        watchbook_enriched=watchbook_enriched,
    )
    body_json = dict(body_json)
    if index_tech:
        body_json["index_multi_tf"] = {
            "symbol": primary,
            "M": index_tech.get("M"),
            "W": index_tech.get("W"),
            "D": index_tech.get("D"),
        }
    body_json["liquidity_note"] = session_facts.get("liquidity_line")
    body_json["foreign_prop_note"] = session_facts.get("foreign_prop_line") or (
        "thiếu dữ liệu NN/tự doanh trong payload — nêu rõ là thiếu, không bịa"
    )
    body, engine = maybe_gemini_rewrite(
        config=config,
        title=title,
        rule_markdown=body,
        body_json=body_json,
    )
    # Chỉ gắn nhãn khi Gemini thành công (không gắn trên fallback Mode 1).
    if engine == "gemini":
        title = apply_ai_title_suffix(title)
        body = sync_body_title_line(body, title)
    body_json = dict(body_json)
    body_json["engine"] = engine
    saved = save_daily_brief(
        brief_date=day.isoformat(),
        title=title,
        body_markdown=body,
        body_json=body_json,
        tech_appendix=tech_rows,
        db_path=db_path,
    )
    logger.info(
        "[DBG-%s-MORNING-BRIEF] ok date=%s watch=%s tech=%s engine=%s",
        datetime.now(ZoneInfo(TZ_NAME)).strftime("%Y%m%d-%H%M"),
        day.isoformat(),
        len(watchbook),
        len(tech_rows),
        engine,
    )
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate ATZ morning brief into signals.db")
    parser.add_argument("--date", help="ISO date YYYY-MM-DD (default: VN today)")
    parser.add_argument("--bars-dir", default=None, help="OHLCV CSV directory")
    parser.add_argument("--db", default=None, help="SQLite path (default SIGNALS_DB_PATH)")
    parser.add_argument("--seed", default=None, help="Optional watchbook YAML seed")
    args = parser.parse_args(argv)

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    day = date.fromisoformat(args.date) if args.date else None
    bars = Path(args.bars_dir) if args.bars_dir else None
    db = Path(args.db) if args.db else None
    seed = Path(args.seed) if args.seed else None
    try:
        result = generate_morning_brief(brief_date=day, bars_dir=bars, db_path=db, seed_yaml=seed)
    except Exception as exc:
        logger.error("ERR-BRIEF-000 generate failed: %s", exc)
        print(f"ERR-BRIEF-000: {exc}", file=sys.stderr)
        return 1
    print(result.get("title") or "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
