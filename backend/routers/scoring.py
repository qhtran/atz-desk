"""Scoring Matrix API — ``/api/scoring`` (decision support, no order placement).

Also aliases ``POST /api/rules`` and ``POST /api/evaluate`` per CDA paths.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.desk_scoring_engine import DEFAULT_SEED_RULES, decision_label_vi, evaluate_rules
from backend.desk_scoring_presets import get_preset_rules, list_presets
from backend.desk_scoring_store import (
    init_desk_scoring_store,
    latest_symbol_score,
    list_rules,
    save_symbol_score,
    upsert_rule,
)
from backend.desk_session import COOKIE_NAME as DESK_COOKIE
from backend.identity import resolve_me

router = APIRouter(tags=["desk-scoring"])


class RuleUpsertBody(BaseModel):
    rule_code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    weight: float = Field(...)
    condition_json: dict[str, Any] | list[Any] = Field(...)
    category: str = Field(default="general", max_length=64)
    is_active: bool = True

    @field_validator("rule_code")
    @classmethod
    def _code_upper(cls, v: str) -> str:
        s = str(v or "").strip().upper()
        if not s:
            raise ValueError("rule_code required")
        return s


class EvaluateBody(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    indicators: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    # YAML catalog profile — isolated from SQLite scoring_rules
    profile: str | None = Field(default=None, max_length=64)

    @field_validator("symbol")
    @classmethod
    def _sym_upper(cls, v: str) -> str:
        s = str(v or "").strip().upper()
        if not s:
            raise ValueError("symbol required")
        return s

    @field_validator("profile")
    @classmethod
    def _profile_norm(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower().replace("-", "_")
        return s or None


def _require_user(request: Request) -> str:
    me = resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


def _ensure_seed_rules() -> None:
    """Idempotent seed when matrix empty."""
    init_desk_scoring_store()
    if list_rules(active_only=False):
        return
    for raw in DEFAULT_SEED_RULES:
        upsert_rule(
            rule_code=raw["rule_code"],
            name=raw["name"],
            weight=float(raw["weight"]),
            condition_json=raw["condition_json"],
            category=str(raw.get("category") or "general"),
            is_active=bool(raw.get("is_active", True)),
        )


def _public_rule(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "rule_code": item["rule_code"],
        "category": item["category"],
        "name": item["name"],
        "weight": item["weight"],
        "condition_json": item["condition_json"],
        "is_active": item["is_active"],
        "updated_at": item.get("updated_at"),
    }


def _do_upsert_rule(body: RuleUpsertBody) -> dict:
    try:
        item = upsert_rule(
            rule_code=body.rule_code,
            name=body.name,
            weight=body.weight,
            condition_json=body.condition_json,
            category=body.category,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": _public_rule(item)}


def _do_evaluate(body: EvaluateBody) -> dict:
    """Evaluate against YAML preset catalog — does not mutate shared scoring_rules."""
    try:
        profile_id, rules = get_preset_rules(body.profile)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown scoring profile: {exc}") from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result = evaluate_rules(rules, body.indicators or {})
    saved = None
    if body.persist:
        # Persist still writes score history; rules DB untouched.
        init_desk_scoring_store()
        saved = save_symbol_score(
            symbol=body.symbol,
            total_score=result["total_score"],
            max_score=result["max_score"],
            score_pct=result["score_pct"],
            decision=result["decision"],
            breakdown=result["breakdown"],
            indicators={**(body.indicators or {}), "_profile": profile_id},
        )
    return {
        "ok": True,
        "symbol": body.symbol,
        "profile": profile_id,
        "total_score": result["total_score"],
        "max_score": result["max_score"],
        "score_pct": result["score_pct"],
        "decision": result["decision"],
        "decision_label": result.get("decision_label")
        or decision_label_vi(str(result.get("decision") or "")),
        "breakdown": result["breakdown"],
        "saved_id": saved["id"] if saved else None,
        "disclaimer": "Tham khảo định lượng — không phải lệnh mua/bán tự động.",
    }


# ---- /api/scoring/* ----
@router.get("/api/scoring/presets")
def api_list_scoring_presets() -> dict:
    try:
        catalog = list_presets()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, **catalog}


@router.get("/api/scoring/rules")
def api_list_scoring_rules(active_only: bool = True) -> dict:
    _ensure_seed_rules()
    items = list_rules(active_only=active_only)
    return {"ok": True, "items": [_public_rule(i) for i in items]}


@router.post("/api/scoring/rules", status_code=201)
def api_upsert_scoring_rule(request: Request, body: RuleUpsertBody) -> dict:
    _require_user(request)
    return _do_upsert_rule(body)


@router.post("/api/scoring/evaluate")
def api_scoring_evaluate(body: EvaluateBody) -> dict:
    return _do_evaluate(body)


@router.get("/api/scoring/symbols/{symbol}")
def api_latest_symbol_score(symbol: str) -> dict:
    item = latest_symbol_score(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="No score yet")
    return {
        "ok": True,
        "item": {
            "id": item["id"],
            "symbol": item["symbol"],
            "total_score": item["total_score"],
            "max_score": item["max_score"],
            "score_pct": item["score_pct"],
            "decision": item["decision"],
            "breakdown": item["breakdown"],
            "indicators": item["indicators"],
            "created_at": item["created_at"],
        },
    }


# ---- CDA aliases ----
@router.post("/api/rules", status_code=201)
def api_rules_alias(request: Request, body: RuleUpsertBody) -> dict:
    _require_user(request)
    return _do_upsert_rule(body)


@router.post("/api/evaluate")
def api_evaluate_alias(body: EvaluateBody) -> dict:
    return _do_evaluate(body)
