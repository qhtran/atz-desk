"""Contract: cột XHT dùng cùng pipeline spark như card VNINDEX."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "frontend" / "index.html"


def _fn_body(src: str, name: str) -> str:
    """Rough extract of a function body until the next top-level function at same indent."""
    m = re.search(rf"function {re.escape(name)}\s*\([^)]*\)\s*\{{", src)
    assert m, f"missing function {name}"
    start = m.end()
    depth = 1
    i = start
    while i < len(src) and depth:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return src[start : i - 1]


def test_xht_and_vnindex_share_spark_render_pipeline():
    src = INDEX_HTML.read_text(encoding="utf-8")
    assert "function renderSparkSvg(" in src
    assert "function sparkGeom(" in src
    assert "function sparkPointsFor(" in src
    assert "function sparkLevelsFromRow(" in src
    assert "function pushSpark(" in src
    assert "function mergeSparkSeriesPayload(" in src
    assert "function fetchEquitySpark(" in src
    assert "function fetchIndexSpark(" in src

    xht = _fn_body(src, "refreshEquitySparkCell")
    assert "sparkPointsFor(" in xht
    assert "sparkLevelsFromRow(" in xht
    assert "renderSparkSvg(" in xht

    idx = _fn_body(src, "idxCardHtml")
    assert "sparkPointsFor(" in idx
    assert "sparkLevelsFromRow(" in idx
    assert "renderSparkSvg(" in idx

    apply_idx = _fn_body(src, "applyIndex")
    assert "pushSpark(" in apply_idx
    assert "patchSparkSvg(" in apply_idx
    assert "sparkPointsFor(" in apply_idx

    apply_eq = _fn_body(src, "applyEquity")
    assert "pushSpark(" in apply_eq
    assert "refreshEquitySparkCell(" in apply_eq

    fetch_eq = _fn_body(src, "fetchEquitySpark")
    assert "/api/iboard/equity-spark" in fetch_eq
    assert "mergeSparkSeriesPayload(" in fetch_eq
    assert "scheduleEquitySparkRefresh(" in fetch_eq

    fetch_idx = _fn_body(src, "fetchIndexSpark")
    assert "/api/iboard/index-spark" in fetch_idx
    assert "mergeSparkSeriesPayload(" in fetch_idx


def test_snapshot_hydrates_equity_spark_with_index_spark():
    src = INDEX_HTML.read_text(encoding="utf-8")
    assert "Promise.all([fetchIndexSpark(), fetchEquitySpark(equitySyms)])" in src
    assert 'data-f="trendSpark"' in src
