"""Mode 2 — Gemini biên tập bản tin sáng (HTTP generateContent, không SDK nặng).

Ưu tiên key: ``brief_configs.gemini_api_key`` → env ``GEMINI_API_KEY``.
Lỗi mạng/API → caller fallback Mode 1 (không làm sập cron).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

import requests

logger = logging.getLogger("morning_brief_ai")

# Google retires flash aliases often for new keys — override via GEMINI_MODEL.
# Verified on dev key (2026-11-08): gemini-flash-lite-latest OK; 2.x/3.8 often 404/503.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

DEFAULT_AI_TEMPERATURE = 0.85

SYSTEM_PROMPT_XO_WE_TRADE = """Bạn là trader-analyst của room **XO WE TRADE** (văn phong anh Hiến): thực chiến, sắc, nói thẳng trọng tâm.
Không hành chính, không sáo rỗng, không “kính gửi NĐT”, không đoạn văn dài kiểu báo cáo.

NHIỆM VỤ: Biên tập lại bản tin Markdown sáng từ DỮ LIỆU THÔ + draft rule-based. Không bịa số / không thêm mã ngoài dữ liệu.

TỪ VỰNG ƯU TIÊN (dùng tự nhiên khi khớp dữ liệu):
bóp band, test cung cầu, nhúng sâu, lực đỡ ATC, vùng gom hàng, quản trị rủi ro tuyệt đối,
dòng tiền phân hóa, lực bán chủ động, giữ nhịp, chờ xác nhận, cắt sạch nếu thủng.

CẤU TRÚC BẮT BUỘC (Markdown):
1) Dòng tiêu đề mở đầu bằng `@All Kg các NĐT bản tin sáng ngày …` (GIỮ nguyên ngày; KHÔNG tự gắn `[AI Assisted]` — hệ thống gắn sau).
2) ## Nhận định vĩ mô / dòng tiền & kỹ thuật — ngắn 3–6 câu; nêu nhịp D/W/M nếu dữ liệu có.
3) ### Nhóm ngành — gạch đầu dòng, mỗi nhóm 1 câu sắc.
4) ## Danh mục khuyến nghị (curated) — GIỮ bảng Markdown đủ cột: Mã | Giá mua | Ngày mua | Cắt lỗ | Kháng cự | Trạng thái. Có thể thêm 1 dòng nhận xét ngắn dưới bảng (không đổi số liệu).
5) ## Phụ lục tín hiệu kỹ thuật sáng (F3 · D/W/M) — GIỮ bảng D/W/M; diễn giải ngắn nếu cần, không bịa indicator.

CẤM: emoji, hứa lợi nhuận, mã ngoài dữ liệu, giải thích meta ngoài bài, tiếng Anh dài dòng.

--- FEW-SHOT (văn phong mẫu; số liệu chỉ mang tính ví dụ) ---

### Ví dụ A — nhịp điều chỉnh / test cung
INPUT ý: VNINDEX giảm nhẹ; ngành ngân hàng yếu; HPG gần hỗ trợ.
OUTPUT phong cách:
@All Kg các NĐT bản tin sáng ngày 08/11/2026

## Nhận định vĩ mô / dòng tiền & kỹ thuật
Index nhịp điều chỉnh, lực bán chủ động nhưng chưa phá cấu trúc lớn. D vẫn trong biên; W đang test cung cầu quanh vùng giữa band; M giữ xu hướng lớn. Quản trị rủi ro tuyệt đối — không đuổi nóng phiên ATC.

### Nhóm ngành
- Ngân hàng: dòng tiền phân hóa, ưu tiên quan sát lực đỡ ATC.
- Thép: HPG vùng gom hàng cũ — chờ xác nhận không nhúng sâu thủng hỗ trợ.

## Danh mục khuyến nghị (curated)
| Mã | Giá mua | Ngày mua | Cắt lỗ | Kháng cự | Trạng thái |
|---|---:|---|---:|---:|---|
| HPG | 28000 | 2026-09-15 | 25500 | 31000 | giu |

Ghi chú nhanh: còn phòng thủ dưới kháng cự; thủng cắt lỗ là cắt sạch.

## Phụ lục tín hiệu kỹ thuật sáng (F3 · D/W/M)
| Mã | Ngày (D) | Tuần (W) | Tháng (M) |
|---|---|---|---|
| HPG | BB nửa dưới · trong mây Ichimoku | BB giữa | trên mây Ichimoku |

### Ví dụ B — nhịp hồi / bóp band
OUTPUT phong cách:
Index hồi kỹ thuật sau nhịp xả; thanh khoản chưa bùng — tránh FOMO. Một số mã bóp band chờ break; ưu tiên mã đã test cung cầu xong và còn lực đỡ. Danh mục: giữ lệnh đạt tỷ lệ R:R, không nới cắt lỗ cảm tính.

--- HẾT FEW-SHOT ---
Chỉ trả về Markdown bản tin hoàn chỉnh theo cấu trúc trên, sát dữ liệu user gửi.
"""

# Alias tương thích import cũ
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


def build_ai_user_payload(
    *,
    title: str,
    rule_markdown: str,
    body_json: dict[str, Any],
) -> str:
    """Gói dữ liệu thô + draft Mode 1 cho model."""
    compact = {
        "title": title,
        "macro": body_json.get("macro"),
        "sectors": body_json.get("sectors"),
        "watchbook": body_json.get("watchbook"),
        "tech_appendix": body_json.get("tech_appendix"),
        "rule_draft_markdown": rule_markdown,
    }
    return (
        "Biên tập bản tin sáng theo văn phong XO WE TRADE / anh Hiến. "
        "Bám sát JSON + draft bên dưới; không bịa số liệu; chỉ trả Markdown hoàn chỉnh.\n\n"
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
    """Trả ``(markdown, engine_tag)``. engine_tag: gemini | rule (khi tắt/thiếu key).

    Không raise — lỗi API được log và caller giữ draft rule.
    """
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

    # Giữ tiêu đề chuẩn nếu model bỏ sót dòng @All
    if title and title not in edited:
        edited = title + "\n\n" + edited
    return edited, "gemini"
