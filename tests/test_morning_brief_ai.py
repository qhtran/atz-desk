"""Mode 2 Gemini rewrite + config masking (no live API)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.morning_brief_ai import call_gemini_edit, maybe_gemini_rewrite
from backend.morning_brief_store import get_config, init_brief_store, public_config, put_config


class _FakeResp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_public_config_masks_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    db = tmp_path / "signals.db"
    init_brief_store(db)
    put_config({"gemini_api_key": "sk-test-ABCDEFGH", "ai_mode_enabled": True}, db_path=db)
    raw = get_config(db)
    assert raw["gemini_api_key"] == "sk-test-ABCDEFGH"
    pub = public_config(db)
    assert pub["gemini_api_key"] == "••••EFGH"
    assert pub["gemini_api_key_set"] is True
    assert pub["ai_mode_enabled"] is True


def test_put_config_ignores_mask_placeholder(tmp_path: Path):
    db = tmp_path / "signals.db"
    put_config({"gemini_api_key": "real-secret-key"}, db_path=db)
    put_config({"gemini_api_key": "••••EFGH"}, db_path=db)
    assert get_config(db)["gemini_api_key"] == "real-secret-key"
    put_config({"gemini_api_key": "__CLEAR__"}, db_path=db)
    assert get_config(db)["gemini_api_key"] == ""


def test_maybe_gemini_rewrite_off_stays_rule():
    md, engine = maybe_gemini_rewrite(
        config={"ai_mode_enabled": False},
        title="t",
        rule_markdown="RULE_DRAFT",
        body_json={},
    )
    assert md == "RULE_DRAFT"
    assert engine == "rule"


def test_maybe_gemini_success_and_fallback():
    def ok_post(*_a, **_k):
        return _FakeResp(
            200,
            {"candidates": [{"content": {"parts": [{"text": "AI_EDITED_MARKDOWN"}]}}]},
        )

    md, engine = maybe_gemini_rewrite(
        config={"ai_mode_enabled": True, "gemini_api_key": "k", "ai_temperature": 0.5},
        title="@All title",
        rule_markdown="RULE",
        body_json={"macro": "m"},
        http_post=ok_post,
    )
    assert "AI_EDITED_MARKDOWN" in md
    assert engine == "gemini"

    def bad_post(*_a, **_k):
        return _FakeResp(500, {"error": "nope"})

    md2, engine2 = maybe_gemini_rewrite(
        config={"ai_mode_enabled": True, "gemini_api_key": "k"},
        title="t",
        rule_markdown="RULE_KEEP",
        body_json={},
        http_post=bad_post,
    )
    assert md2 == "RULE_KEEP"
    assert engine2 == "gemini_fallback_rule"


def test_call_gemini_edit_raises_on_http_error():
    def bad_post(*_a, **_k):
        return _FakeResp(403, {})

    with pytest.raises(RuntimeError, match="ERR-BRIEF-031"):
        call_gemini_edit(api_key="k", user_text="hi", http_post=bad_post)
