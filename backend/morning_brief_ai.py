"""Mode 2 — Gemini biên tập bản tin sáng (HTTP generateContent, không SDK nặng).

Ưu tiên key: ``brief_configs.gemini_api_key`` → env ``GEMINI_API_KEY``.
Lỗi mạng/API → caller fallback Mode 1 (không làm sập cron).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import requests

logger = logging.getLogger("morning_brief_ai")

# Google retires flash aliases often for new keys — override via GEMINI_MODEL.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

DEFAULT_AI_TEMPERATURE = 0.85

SYSTEM_PROMPT_XO_WE_TRADE = """Bạn là trader-analyst của room **XO WE TRADE** (văn phong anh Hiến): thực chiến, sắc, dứt khoát.
Không hành chính, không sáo rỗng, không “kính gửi NĐT”, không báo cáo dài.

NHIỆM VỤ: Biên tập bản tin Markdown sáng từ JSON dữ liệu + draft rule-based.
KHÔNG bịa số liệu. KHÔNG thêm mã ngoài `watchbook_enriched` / tech_appendix.
KHÔNG tự gắn `[AI Assisted]` vào tiêu đề (hệ thống gắn sau).

TỪ VỰNG ƯU TIÊN (khi khớp dữ liệu): bóp band, test cung cầu, nhúng sâu, lực đỡ ATC,
vùng gom hàng, quản trị rủi ro tuyệt đối, dòng tiền phân hóa, giữ nhịp, cắt sạch nếu thủng.

════════════════════════════════════
CẤU TRÚC BẮT BUỘC (Markdown)
════════════════════════════════════

1) Tiêu đề 1 dòng:
`@All Kg các NĐT bản tin sáng ngày DD/MM/YYYY`

2) ## Nhận định thị trường / đa khung (XO WE TRADE)
Mở đầu 2–3 bullet từ `session_facts` (session_line, liquidity_line, foreign_prop_line) — CHỈ số có trong JSON.
Phải có đúng 3 mục con, mỗi mục 2–5 câu sắc (dựa `session_facts.index_tf` / tech_appendix / sectors):

### Khung Tháng (M)
- Đọc nến tháng / vị trí mây Ichimoku / Tenkan–Kijun nếu dữ liệu có.
- Xác nhận xu hướng lớn: đảo chiều / tích lũy / tiếp diễn. Không bịa nếu thiếu.

### Khung Tuần (W)
- Nến tuần trong mây / ngoài mây; bóp band hay test cung cầu.
- Dự báo nhịp tuần tới: giữ / quan sát / tránh đuổi nóng.

### Khung Ngày (D)
- Nhịp phiên: sideway trong band hướng xuống/lên, nhúng sâu, lực đỡ ATC nếu khớp dữ liệu.
- GTGD / NN / tự doanh CHỈ lấy từ `session_facts` (hoặc foreign_prop_note / liquidity_note); thiếu → «thiếu dữ liệu — bỏ qua».
- Lực đỡ cổ phiếu trụ nếu sectors/tech có.
- Kết: 1 dòng `forecast_line` + `Kế hoạch giao dịch: {session_facts.plan}`.

3) ### Nhóm ngành
Gạch đầu dòng, mỗi ngành 1 câu (nếu sectors có).

4) ## Danh mục khuyến nghị (Watchbook chuẩn)
Bảng Markdown ĐÚNG cột (theo thứ tự):

| TT | Mã CP | Giá Hiện Tại | Ngày KN | GD T+ | Giá Mua | Giá Cắt Lỗ (5%) | Hỗ trợ kỹ thuật | Kháng cự KT (Mục tiêu giá) | LN Tạm Tính | (%) | Khuyến nghị |

Quy tắc cột (bám `watchbook_enriched`, không bịa):
- TT: số thứ tự 1..n
- Giá Hiện Tại / Giá Mua / Cắt lỗ 5% / Hỗ trợ / Kháng cự / LN Tạm Tính / (%): lấy từ JSON (đã tính sẵn)
- Ngày KN = buy_date; GD T+ = gd_t_plus
- Khuyến nghị: 1 cụm ngắn theo status + kỹ thuật (VD: «Giữ — chờ xác nhận», «Theo dõi sát cắt lỗ», «Chốt dần gần kháng cự»)

5) ## Phụ lục tín hiệu kỹ thuật sáng (F3 · D/W/M)
Giữ bảng | Mã | Ngày (D) | Tuần (W) | Tháng (M) | từ tech_appendix.

CẤM: emoji, hứa lợi nhuận, tiếng Anh dài, giải thích meta ngoài bài.

--- FEW-SHOT (số liệu ví dụ) ---
@All Kg các NĐT bản tin sáng ngày 08/11/2026

## Nhận định đa khung (XO WE TRADE)

### Khung Tháng (M)
Xu hướng lớn còn giữ nhịp tăng tích lũy; Tenkan trên Kijun, giá nghiêng trên mây. Chưa có tín hiệu đảo chiều rõ — quản trị rủi ro tuyệt đối khi M bắt đầu bóp band.

### Khung Tuần (W)
Tuần test cung cầu quanh biên giữa; nến trong/áp mây. Ưu tiên quan sát lực đỡ ATC, tránh FOMO đầu tuần.

### Khung Ngày (D)
D sideway trong band hướng xuống nhẹ; thanh khoản chưa bùng. Thiếu dữ liệu NN/tự doanh — bỏ qua. Trụ còn đỡ điểm số; danh mục chỉ giữ lệnh còn R:R.

### Nhóm ngành
- Ngân hàng: dòng tiền phân hóa.
- Thép: vùng gom hàng — chờ không nhúng sâu thủng hỗ trợ.

## Danh mục khuyến nghị (Watchbook chuẩn)
| TT | Mã CP | Giá Hiện Tại | Ngày KN | GD T+ | Giá Mua | Giá Cắt Lỗ (5%) | Hỗ trợ kỹ thuật | Kháng cự KT (Mục tiêu giá) | LN Tạm Tính | (%) | Khuyến nghị |
|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | HPG | 27500 | 2026-09-15 | T+2.5 ~ 2026-09-18 | 28000 | 26600 | 25500 | 31000 | -500 | -1.8% | Giữ — test hỗ trợ, thủng cắt sạch |

## Phụ lục tín hiệu kỹ thuật sáng (F3 · D/W/M)
| Mã | Ngày (D) | Tuần (W) | Tháng (M) |
|---|---|---|---|
| HPG | BB nửa dưới · trong mây | BB giữa | trên mây Ichimoku |
--- HẾT FEW-SHOT ---

Chỉ trả về Markdown hoàn chỉnh theo cấu trúc trên.
"""

SYSTEM_PROMPT_HIEN = SYSTEM_PROMPT_XO_WE_TRADE


def resolve_gemini_api_key(config: dict[str, Any]) -> str | None:
    stored = str(config.get("gemini_api_key") or "").strip()
    if stored:
        return stored
    env = str(os.getenv("GEMINI_API_KEY") or "").strip()
    return env or None


def clamp_temperature(raw: Any, default: float = DEFAULT_AI_TEMPERATURE) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return min(max(value, 0.1), 1.0)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _parse_buy_date(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def estimate_t_plus_label(buy_date_raw: Any, *, lag_days: int = 3) -> str:
    """Nhãn GD T+ (xấp xỉ lịch; VN thường T+2.5 phiên)."""
    day = _parse_buy_date(buy_date_raw)
    if day is None:
        return "T+2.5"
    settle = day + timedelta(days=max(1, int(lag_days)))
    return f"T+2.5 ~ {settle.isoformat()}"


def enrich_watchbook_for_ai(
    watchbook: list[dict[str, Any]],
    *,
    tech_rows: list[dict[str, Any]] | None = None,
    bars_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Bổ sung cột chuẩn Fireant/XO để Gemini không bịa số."""
    from backend.portfolio_quotes import DEFAULT_BARS_DIR, ohlcv_last_close_vnd

    bars = bars_dir or DEFAULT_BARS_DIR
    tech_by_sym = {
        str(row.get("symbol") or "").upper(): row
        for row in (tech_rows or [])
        if isinstance(row, dict)
    }
    enriched: list[dict[str, Any]] = []
    for idx, item in enumerate(watchbook or [], start=1):
        if not isinstance(item, dict):
            continue
        sym = str(item.get("symbol") or "").strip().upper()
        if not sym:
            continue
        buy = _as_float(item.get("buy_price"))
        last = ohlcv_last_close_vnd(Path(bars), sym)
        stop_given = _as_float(item.get("stop_loss"))
        stop_5 = round(buy * 0.95, 2) if buy and buy > 0 else None
        resist = _as_float(item.get("resistance"))
        support = stop_given if stop_given is not None else stop_5
        pnl = None
        pnl_pct = None
        if last is not None and buy is not None and buy != 0:
            pnl = round(last - buy, 2)
            pnl_pct = round((last - buy) / buy * 100, 2)
        tech = tech_by_sym.get(sym) or {}
        status = str(item.get("status") or "giu")
        if status == "cham_cat_lo":
            khuyen_nghi = "Cắt / phòng thủ — đã chạm cắt lỗ"
        elif status == "cham_khang_cu":
            khuyen_nghi = "Chốt dần gần kháng cự"
        elif status == "theo_doi":
            khuyen_nghi = "Theo dõi sát — chờ xác nhận"
        else:
            khuyen_nghi = "Giữ — quản trị rủi ro tuyệt đối"

        enriched.append(
            {
                "tt": idx,
                "symbol": sym,
                "last_price": last,
                "buy_date": item.get("buy_date"),
                "gd_t_plus": estimate_t_plus_label(item.get("buy_date")),
                "buy_price": buy,
                "stop_loss_5pct": stop_5,
                "stop_loss_book": stop_given,
                "support_kt": support,
                "resistance_kt": resist,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "status": status,
                "note": item.get("note"),
                "tech_D": tech.get("D"),
                "tech_W": tech.get("W"),
                "tech_M": tech.get("M"),
                "khuyen_nghi_goi_y": khuyen_nghi,
            }
        )
    return enriched


def build_ai_user_payload(
    *,
    title: str,
    rule_markdown: str,
    body_json: dict[str, Any],
) -> str:
    """Gói dữ liệu thô + draft Mode 1 cho model."""
    compact = {
        "title": title,
        "session_facts": body_json.get("session_facts") or {},
        "macro": body_json.get("macro"),
        "sectors": body_json.get("sectors"),
        "watchbook_enriched": body_json.get("watchbook_enriched") or body_json.get("watchbook"),
        "tech_appendix": body_json.get("tech_appendix"),
        "index_multi_tf": body_json.get("index_multi_tf"),
        "liquidity_note": body_json.get("liquidity_note"),
        "foreign_prop_note": body_json.get(
            "foreign_prop_note",
            "thiếu dữ liệu NN/tự doanh trong payload — nêu rõ là thiếu, không bịa",
        ),
        "rule_draft_markdown": rule_markdown,
        "output_table_columns": [
            "TT",
            "Mã CP",
            "Giá Hiện Tại",
            "Ngày KN",
            "GD T+",
            "Giá Mua",
            "Giá Cắt Lỗ (5%)",
            "Hỗ trợ kỹ thuật",
            "Kháng cự KT (Mục tiêu giá)",
            "LN Tạm Tính",
            "(%)",
            "Khuyến nghị",
        ],
    }
    return (
        "Biên tập bản tin sáng chuẩn XO WE TRADE: đa khung M/W/D + bảng Watchbook đủ cột. "
        "Bám sát JSON; không bịa số; chỉ trả Markdown hoàn chỉnh.\n\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)
    )


def call_gemini_edit(
    *,
    api_key: str,
    user_text: str,
    temperature: float = DEFAULT_AI_TEMPERATURE,
    model: str | None = None,
    http_post: Callable[..., Any] | None = None,
    timeout_sec: float = 90.0,
    max_retries: int = 2,
) -> str:
    """Gọi Gemini generateContent; trả về text Markdown. Raise RuntimeError nếu lỗi."""
    import time

    model_id = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    url = GEMINI_URL_TMPL.format(model=model_id)
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_XO_WE_TRADE}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": clamp_temperature(temperature),
            "maxOutputTokens": 8192,
        },
    }
    post = http_post or requests.post
    last_err: Exception | None = None
    for attempt in range(max(1, int(max_retries) + 1)):
        try:
            resp = post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=timeout_sec,
            )
        except requests.RequestException as exc:
            last_err = RuntimeError(f"ERR-BRIEF-030: Gemini network error: {exc}")
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last_err from exc

        try:
            data = resp.json()
        except ValueError as exc:
            if resp.status_code >= 400:
                raise RuntimeError(f"ERR-BRIEF-031: Gemini HTTP {resp.status_code}") from exc
            raise RuntimeError("ERR-BRIEF-032: Gemini response not JSON") from exc

        if resp.status_code in (429, 503) and attempt < max_retries:
            time.sleep(1.5 * (attempt + 1))
            continue

        if resp.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else None
            detail = ""
            if isinstance(err, dict):
                detail = str(err.get("status") or "")
                msg = str(err.get("message") or "").replace(api_key, "***")[:160]
                if msg:
                    detail = f"{detail}: {msg}" if detail else msg
            raise RuntimeError(f"ERR-BRIEF-031: Gemini HTTP {resp.status_code} {detail}".strip())

        candidates = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("ERR-BRIEF-033: Gemini empty candidates")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list) or not parts:
            raise RuntimeError("ERR-BRIEF-033: Gemini empty parts")
        texts = [str(p.get("text") or "") for p in parts if isinstance(p, dict)]
        joined = "\n".join(t for t in texts if t.strip()).strip()
        if not joined:
            raise RuntimeError("ERR-BRIEF-033: Gemini empty text")
        return joined

    if last_err:
        raise last_err
    raise RuntimeError("ERR-BRIEF-031: Gemini retries exhausted")


def maybe_gemini_rewrite(
    *,
    config: dict[str, Any],
    title: str,
    rule_markdown: str,
    body_json: dict[str, Any],
    http_post: Callable[..., Any] | None = None,
) -> tuple[str, str]:
    """Trả ``(markdown, engine_tag)``. Không raise — lỗi API → fallback Mode 1."""
    if not bool(config.get("ai_mode_enabled")):
        return rule_markdown, "rule"

    api_key = resolve_gemini_api_key(config)
    if not api_key:
        logger.warning("ERR-BRIEF-034: ai_mode_enabled but no GEMINI_API_KEY / stored key")
        return rule_markdown, "rule_missing_key"

    user_text = build_ai_user_payload(
        title=title,
        rule_markdown=rule_markdown,
        body_json=body_json,
    )
    try:
        edited = call_gemini_edit(
            api_key=api_key,
            user_text=user_text,
            temperature=clamp_temperature(config.get("ai_temperature"), DEFAULT_AI_TEMPERATURE),
            http_post=http_post,
        )
    except RuntimeError as exc:
        logger.error("%s — fallback Mode 1", exc)
        return rule_markdown, "gemini_fallback_rule"

    if title and title not in edited:
        edited = title + "\n\n" + edited
    return edited, "gemini"
