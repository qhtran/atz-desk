"""Morning brief store + engine (hybrid curated + F3 appendix)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backend.morning_brief import (
    AI_TITLE_SUFFIX,
    apply_ai_title_suffix,
    evaluate_watch_status,
    generate_morning_brief,
    render_brief_markdown,
    resample_ohlcv,
    sync_body_title_line,
)
from backend.morning_brief_store import (
    STATUS_HOLD,
    STATUS_RESIST,
    STATUS_STOP,
    get_brief_by_date,
    get_config,
    get_latest_brief,
    init_brief_store,
    list_watchbook,
    put_config,
    replace_watchbook,
    save_daily_brief,
    upsert_watch_item,
)


def _write_bars(path: Path, symbol: str, closes: list[float]) -> None:
    rows = []
    for i, close in enumerate(closes):
        day = 1 + (i % 28)
        month = 1 + (i // 28) % 12
        year = 2024 + (i // 28) // 12
        rows.append(
            {
                "time": f"{year}-{month:02d}-{day:02d}",
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 1_000_000,
            }
        )
    frame = pd.DataFrame(rows)
    path.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path / f"{symbol}.csv", index=False)


def test_store_config_and_watchbook_crud(tmp_path: Path):
    db = tmp_path / "signals.db"
    init_brief_store(db)
    cfg = put_config({"enabled": True, "index_symbols": ["VNINDEX"]}, db_path=db)
    assert cfg["enabled"] is True
    assert cfg["index_symbols"] == ["VNINDEX"]
    assert get_config(db)["timezone"] == "Asia/Ho_Chi_Minh"

    item = upsert_watch_item(
        symbol="fpt",
        buy_price=95_000,
        buy_date="2026-10-01",
        stop_loss=88_000,
        resistance=105_000,
        db_path=db,
    )
    assert item["symbol"] == "FPT"
    assert item["status"] == STATUS_HOLD
    assert len(list_watchbook(db_path=db)) == 1

    replace_watchbook(
        [
            {
                "symbol": "HPG",
                "buy_price": 28_000,
                "stop_loss": 25_000,
                "resistance": 31_000,
                "status": "giu",
            }
        ],
        db_path=db,
    )
    book = list_watchbook(db_path=db)
    assert len(book) == 1
    assert book[0]["symbol"] == "HPG"


def test_daily_brief_unique_by_date(tmp_path: Path):
    db = tmp_path / "signals.db"
    save_daily_brief(
        brief_date="2026-11-08",
        title="t1",
        body_markdown="a",
        body_json={"n": 1},
        tech_appendix=[{"symbol": "FPT"}],
        db_path=db,
    )
    save_daily_brief(
        brief_date="2026-11-08",
        title="t2",
        body_markdown="b",
        db_path=db,
    )
    item = get_brief_by_date("2026-11-08", db_path=db)
    assert item is not None
    assert item["title"] == "t2"
    assert get_latest_brief(db_path=db)["title"] == "t2"


def test_evaluate_watch_status_levels():
    assert evaluate_watch_status(100.0, 90.0, 110.0) == STATUS_HOLD
    assert evaluate_watch_status(85.0, 90.0, 110.0) == STATUS_STOP
    assert evaluate_watch_status(120.0, 90.0, 110.0) == STATUS_RESIST


def test_resample_and_render_sections(tmp_path: Path):
    closes = [20.0 + (i % 5) * 0.1 for i in range(120)]
    _write_bars(tmp_path, "VNINDEX", closes)
    bars = pd.read_csv(tmp_path / "VNINDEX.csv")
    weekly = resample_ohlcv(bars, "W-FRI")
    monthly = resample_ohlcv(bars, "ME")
    assert weekly is not None and len(weekly) >= 5
    assert monthly is not None and len(monthly) >= 2

    title, body, payload = render_brief_markdown(
        brief_date=date(2026, 11, 8),
        config={"title_template": "@All Kg các NĐT bản tin sáng ngày {date}"},
        watchbook=[
            {
                "symbol": "FPT",
                "buy_price": 95_000,
                "buy_date": "2026-10-01",
                "stop_loss": 88_000,
                "resistance": 105_000,
                "status": "giu",
            }
        ],
        tech_rows=[{"symbol": "FPT", "D": "BB giữa", "W": "trên mây Ichimoku", "M": "—"}],
        macro_line="VNINDEX test",
        sector_lines=["- Ngân hàng (VCB): —"],
    )
    assert "08/11/2026" in title
    assert "## Danh mục khuyến nghị (Watchbook chuẩn)" in body
    assert "Giá Cắt Lỗ (5%)" in body
    assert "## Phụ lục tín hiệu kỹ thuật sáng" in body
    assert "FPT" in body
    assert payload["macro"] == "VNINDEX test"


def test_generate_morning_brief_writes_db(tmp_path: Path):
    bars = tmp_path / "ohlcv"
    # Enough bars for BB (20) + basic Ichimoku path; monthly may be thin.
    closes = [100.0 + (i % 7) * 0.2 for i in range(80)]
    _write_bars(bars, "VNINDEX", closes)
    for sym in ("FPT", "HPG", "MBB", "VCB", "SSI"):
        _write_bars(bars, sym, closes)

    db = tmp_path / "signals.db"
    seed = Path(__file__).resolve().parents[1] / "config" / "morning_brief_watchbook.yaml"
    result = generate_morning_brief(
        brief_date=date(2026, 11, 8),
        bars_dir=bars,
        db_path=db,
        seed_yaml=seed,
    )
    assert result["brief_date"] == "2026-11-08"
    assert "bản tin sáng" in result["title"]
    assert "Danh mục khuyến nghị" in result["body_markdown"]
    assert isinstance(result["tech_appendix"], list)
    assert get_latest_brief(db_path=db) is not None


def test_generate_fails_without_index_ohlcv(tmp_path: Path):
    db = tmp_path / "signals.db"
    with pytest.raises(RuntimeError, match="ERR-BRIEF-011"):
        generate_morning_brief(
            brief_date=date(2026, 11, 8),
            bars_dir=tmp_path / "empty",
            db_path=db,
            seed_yaml=tmp_path / "missing.yaml",
        )


def test_ai_title_suffix_helpers():
    base = "@All Kg các NĐT bản tin sáng ngày 08/11/2026"
    labeled = apply_ai_title_suffix(base)
    assert labeled.endswith(AI_TITLE_SUFFIX.strip())
    assert apply_ai_title_suffix(labeled) == labeled  # idempotent
    body = sync_body_title_line(base + "\n\n## Macro\nhello", labeled)
    assert body.startswith(labeled)
    assert "## Macro" in body
    assert body.count("[AI Assisted]") == 1


def test_macro_override_and_disabled(tmp_path: Path):
    bars = tmp_path / "ohlcv"
    closes = [100.0 + (i % 5) * 0.1 for i in range(40)]
    _write_bars(bars, "VNINDEX", closes)
    for sym in ("FPT", "HPG", "MBB", "VCB", "SSI"):
        _write_bars(bars, sym, closes)
    db = tmp_path / "signals.db"
    put_config({"macro_override": "MACRO_ADMIN_NOTE_XYZ"}, db_path=db)
    seed = Path(__file__).resolve().parents[1] / "config" / "morning_brief_watchbook.yaml"
    result = generate_morning_brief(
        brief_date=date(2026, 11, 9),
        bars_dir=bars,
        db_path=db,
        seed_yaml=seed,
    )
    assert "MACRO_ADMIN_NOTE_XYZ" in result["body_markdown"]
    assert "Ghi chú admin" in result["body_markdown"]
    assert "session_facts" in (result.get("body_json") or {})
    assert "Watchbook chuẩn" in result["body_markdown"]

    put_config({"enabled": False}, db_path=db)
    with pytest.raises(RuntimeError, match="ERR-BRIEF-010"):
        generate_morning_brief(
            brief_date=date(2026, 11, 10),
            bars_dir=bars,
            db_path=db,
            seed_yaml=seed,
        )
