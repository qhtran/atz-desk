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

SYSTEM_PROMPT_HIEN = """Bạn là biên tập viên bản tin chứng khoán Việt Nam buổi sáng (văn phong thực chiến, ngắn gọn, rõ ràng — phong cách Hiến).
Nhiệm vụ: viết lại bản tin Markdown tiếng Việt dựa trên DỮ LIỆU THÔ đã tính sẵn (không bịa số liệu).
Quy tắc:
- Giữ cấu trúc: tiêu đề @All…, nhận định vĩ mô/dòng tiền, bảng danh mục khuyến nghị (cột giữ nguyên), phụ lục kỹ thuật D/W/M.
- Không thêm mã không có trong dữ liệu. Không hứa lợi nhuận. Không dùng emoji.
- Chỉ trả về Markdown hoàn chỉnh, không giải thích ngoài bài.
"""


def resolve_gemini_api_key(config: dict[str, Any]) -> str | None:
    stored = str(config.get("gemini_api_key") or "").strip()
    if stored:
        return stored
    env = str(os.getenv("GEMINI_API_KEY") or "").strip()
    return env or None


def clamp_temperature(raw: Any, default: float = 0.7) -> float:
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
        "Dưới đây là JSON dữ liệu đã tính + bản nháp rule-based. "
        "Hãy biên tập thành bản tin Markdown cuối cùng.\n\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)
    )


def call_gemini_edit(
    *,
    api_key: str,
    user_text: str,
    temperature: float = 0.7,
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
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_HIEN}]},
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
            temperature=clamp_temperature(config.get("ai_temperature"), 0.7),
            http_post=http_post,
        )
    except RuntimeError as exc:
        logger.error("%s — fallback Mode 1", exc)
        return rule_markdown, "gemini_fallback_rule"

    # Giữ tiêu đề chuẩn nếu model bỏ sót dòng @All
    if title and title not in edited:
        edited = title + "\n\n" + edited
    return edited, "gemini"
