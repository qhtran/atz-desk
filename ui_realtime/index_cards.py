"""Thẻ chỉ số kiểu FireAnt: mã + tên, sparkline SVG (vạch tham chiếu vàng, trên xanh / dưới đỏ, chấm cuối), giá trị +/- %.

Không import Streamlit: đọc Redis qua RedisReader (cache trong process) và trả HTML để trang Realtime st.markdown.
"""
from __future__ import annotations

import html
import json
import time

from ui_realtime.log import ERR_UI_INDEX, log
SYMBOLS = ["VNINDEX", "HNXINDEX", "UPCOMINDEX", "VN30", "VN30F1M", "VN30F2M"]
NAMES = {"VNINDEX": "Chỉ số VNINDEX", "HNXINDEX": "Chỉ số HNXINDEX", "UPCOMINDEX": "Chỉ số UPCOMINDEX",
         "VN30": "Chỉ số VN30", "VN30F1M": "Hợp đồng tương lai VN30F1M", "VN30F2M": "Hợp đồng tương lai VN30F2M"}
GREEN, RED, YELLOW, GREY = "#22c55e", "#ef4444", "#eab308", "#9ca3af"
QUOTE_KEY, SPARK_KEY = "idx:quote:{symbol}", "spark:{symbol}"


def read(reader, symbols=SYMBOLS) -> dict | None:
    """{sym: {'quote': dict|None, 'spark': [values]}}; None nếu Redis lỗi."""
    keys = [QUOTE_KEY.format(symbol=s) for s in symbols] + [SPARK_KEY.format(symbol=s) for s in symbols]
    raw = reader._cached(("idx", tuple(keys)), float(reader.u["cache_ttl_seconds"]), lambda: reader.r.mget(keys))
    if raw is None:
        return None
    out, n = {}, len(symbols)
    for i, s in enumerate(symbols):
        try:
            q = json.loads(raw[i]) if raw[i] else None
            sp = json.loads(raw[n + i]) if raw[n + i] else {}
        except ValueError:
            q, sp = None, {}
        out[s] = {"quote": q, "spark": [p[1] for p in sp.get("points", [])]}
    return out


def sparkline_svg(values: list[float], ref: float | None, uid: str, w: int = 120, h: int = 40) -> str:
    """SVG: polyline vẽ 2 lần, clip phần trên vạch ref (xanh) và dưới (đỏ); vạch ref vàng; chấm ở điểm cuối."""
    if not values:
        return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><line x1="0" y1="{h/2}" x2="{w}" y2="{h/2}" stroke="{GREY}" stroke-dasharray="2 3"/></svg>'
    vals = values if len(values) > 1 else values * 2
    ref = vals[0] if ref is None else ref
    lo, hi = min(min(vals), ref), max(max(vals), ref)
    span = (hi - lo) or 1.0
    pad = 3

    def y(v):
        return round(pad + (hi - v) / span * (h - 2 * pad), 2)

    step = (w - 2 * pad) / (len(vals) - 1)
    pts = " ".join(f"{round(pad + i * step, 2)},{y(v)}" for i, v in enumerate(vals))
    ry = y(ref)
    lx, ly = round(pad + (len(vals) - 1) * step, 2), y(vals[-1])
    dot = GREEN if vals[-1] > ref else RED if vals[-1] < ref else YELLOW
    u = html.escape(uid)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><clipPath id="up-{u}"><rect x="0" y="0" width="{w}" height="{ry}"/></clipPath>'
            f'<clipPath id="dn-{u}"><rect x="0" y="{ry}" width="{w}" height="{h - ry}"/></clipPath></defs>'
            f'<line x1="0" y1="{ry}" x2="{w}" y2="{ry}" stroke="{YELLOW}" stroke-width="1"/>'
            f'<polyline points="{pts}" fill="none" stroke="{GREEN}" stroke-width="1.5" clip-path="url(#up-{u})"/>'
            f'<polyline points="{pts}" fill="none" stroke="{RED}" stroke-width="1.5" clip-path="url(#dn-{u})"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2.5" fill="{dot}"/></svg>')


CSS = """<style>
.idx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:6px;margin-bottom:8px}
.idx-card{display:flex;align-items:center;gap:10px;background:#111418;border:1px solid #1f2937;border-radius:8px;padding:6px 10px;color:#e5e7eb;font-family:inherit}
.idx-l{flex:1 1 auto;min-width:0}.idx-code{font-weight:700;font-size:0.95rem}.idx-name{font-size:0.72rem;color:#9ca3af;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.idx-r{text-align:right;min-width:92px}.idx-v{font-weight:700;font-size:0.95rem}.idx-c{font-size:0.75rem}
.idx-stale{font-size:0.68rem;color:#eab308}
</style>"""


def card_html(sym: str, item: dict, now: float, stale_seconds: float) -> str:
    q, spark = item.get("quote"), item.get("spark") or []
    if not q:
        right = '<div class="idx-v">–</div><div class="idx-c" style="color:#9ca3af">chưa có dữ liệu</div>'
        svg = sparkline_svg(spark, None, sym)
        stale = True
    else:
        color = GREEN if q["change"] > 0 else RED if q["change"] < 0 else YELLOW
        right = (f'<div class="idx-v" style="color:{color}">{q["value"]:,.2f}</div>'
                 f'<div class="idx-c" style="color:{color}">{q["change"]:+,.2f} / {q["pct"]:+.2f}%</div>')
        svg = sparkline_svg(spark + ([] if spark and spark[-1] == q["value"] else [q["value"]]) if spark else [q["value"]],
                            q["ref"], sym)
        stale = now - float(q.get("ts") or 0) > stale_seconds
    badge = '<div class="idx-stale">⚠️ cũ</div>' if stale else ""
    return (f'<div class="idx-card" data-sym="{sym}"><div class="idx-l"><div class="idx-code">{sym}</div>'
            f'<div class="idx-name">{html.escape(NAMES.get(sym, sym))}</div>{badge}</div>{svg}'
            f'<div class="idx-r">{right}</div></div>')


def cards_html(items: dict | None, now: float | None = None, stale_seconds: float = 120) -> str:
    now = time.time() if now is None else now
    if items is None:
        return CSS + '<div class="idx-grid"><div class="idx-card">⚠️ Không đọc được chỉ số (Redis đang lỗi), thử lại sau vài giây.</div></div>'
    return CSS + '<div class="idx-grid">' + "".join(card_html(s, items.get(s, {}), now, stale_seconds) for s in SYMBOLS) + "</div>"


_logged = {"down": 0.0}


def render_html(reader, stale_seconds: float, user_id=None) -> str:
    items = reader and read(reader)
    if items is None and time.time() - _logged["down"] > 60:
        _logged["down"] = time.time()
        log("INDEX", "index cards fallback: redis unavailable", error_code=ERR_UI_INDEX, user_id=user_id)
    return cards_html(items, stale_seconds=stale_seconds)
