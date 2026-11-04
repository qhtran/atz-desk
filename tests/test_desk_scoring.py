"""Scoring Matrix engine + /api/scoring endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.desk_scoring_engine import (
    DEFAULT_SEED_RULES,
    decision_from_score_pct,
    evaluate_rules,
)
from backend.desk_scoring_store import (
    init_desk_scoring_store,
    latest_symbol_score,
    list_rules,
    save_symbol_score,
    upsert_rule,
)
from backend.main import app


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "desk_scoring.db"
    init_desk_scoring_store(path)
    return path


def test_decision_bands():
    assert decision_from_score_pct(95) == "STRONG_BUY"
    assert decision_from_score_pct(80) == "STRONG_BUY"
    assert decision_from_score_pct(60) == "ACCUMULATE"
    assert decision_from_score_pct(40) == "HOLD"
    assert decision_from_score_pct(20) == "TRIM"
    assert decision_from_score_pct(5) == "SELL"


def test_evaluate_rules_hit_and_miss(db: Path):
    rules = [
        {
            "rule_code": "RSI_OK",
            "category": "m",
            "name": "RSI",
            "weight": 40,
            "is_active": True,
            "condition_json": {"field": "rsi", "op": "between", "value": [40, 65]},
        },
        {
            "rule_code": "TREND",
            "category": "t",
            "name": "MA",
            "weight": 60,
            "is_active": True,
            "condition_json": {"field": "price_vs_ma20", "op": "gt", "value": 0},
        },
    ]
    # both hit → 100%
    r = evaluate_rules(rules, {"rsi": 55, "price_vs_ma20": 1.5})
    assert r["total_score"] == pytest.approx(100)
    assert r["score_pct"] == pytest.approx(100)
    assert r["decision"] == "STRONG_BUY"
    assert all(b["hit"] for b in r["breakdown"])

    # only RSI → 40%
    r2 = evaluate_rules(rules, {"rsi": 50, "price_vs_ma20": -1})
    assert r2["total_score"] == pytest.approx(40)
    assert r2["score_pct"] == pytest.approx(40)
    assert r2["decision"] == "HOLD"


def test_store_upsert_and_score_history(db: Path):
    a = upsert_rule(
        rule_code="rsi_ok",
        name="RSI band",
        weight=20,
        condition_json={"field": "rsi", "op": "gte", "value": 45},
        db_path=db,
    )
    assert a["rule_code"] == "RSI_OK"
    b = upsert_rule(
        rule_code="RSI_OK",
        name="RSI band v2",
        weight=25,
        condition_json={"field": "rsi", "op": "gte", "value": 50},
        db_path=db,
    )
    assert b["id"] == a["id"]
    assert b["weight"] == 25
    assert len(list_rules(db_path=db)) == 1

    saved = save_symbol_score(
        symbol="fpt",
        total_score=25,
        max_score=25,
        score_pct=100,
        decision="STRONG_BUY",
        breakdown=[{"rule_code": "RSI_OK", "hit": True}],
        indicators={"rsi": 55},
        db_path=db,
    )
    latest = latest_symbol_score("FPT", db_path=db)
    assert latest is not None and latest["id"] == saved["id"]
    assert latest["decision"] == "STRONG_BUY"


def test_default_seed_rules_shape():
    assert len(DEFAULT_SEED_RULES) >= 3
    codes = {r["rule_code"] for r in DEFAULT_SEED_RULES}
    assert "RSI_OK" in codes


def test_api_evaluate_and_rules(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_scoring.db"
    import backend.desk_scoring_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_scoring_store(path)
    client = TestClient(app)

    # evaluate seeds rules automatically
    res = client.post(
        "/api/scoring/evaluate",
        json={
            "symbol": "FPT",
            "indicators": {
                "rsi": 52,
                "price_vs_ma20": 1.0,
                "macd_hist": 0.2,
                "vol_ratio": 1.5,
                "change_pct": 1.2,
            },
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["symbol"] == "FPT"
    assert body["decision"] in {"STRONG_BUY", "ACCUMULATE", "HOLD", "TRIM", "SELL"}
    assert isinstance(body["breakdown"], list) and len(body["breakdown"]) >= 3
    assert body["score_pct"] >= 80  # all seed rules should hit with these indicators

    # alias path
    alias = client.post(
        "/api/evaluate",
        json={"symbol": "HPG", "indicators": {"rsi": 10}, "persist": False},
    )
    assert alias.status_code == 200
    assert alias.json()["decision"] in {"HOLD", "TRIM", "SELL", "ACCUMULATE", "STRONG_BUY"}

    # rules write requires auth
    assert client.post(
        "/api/scoring/rules",
        json={
            "rule_code": "X",
            "name": "x",
            "weight": 1,
            "condition_json": {"field": "rsi", "op": "gt", "value": 0},
        },
    ).status_code == 401

    headers = {"X-Authentik-Username": "hoa", "X-Authentik-Groups": "members"}
    created = client.post(
        "/api/rules",
        headers=headers,
        json={
            "rule_code": "custom_vol",
            "name": "Vol spike",
            "weight": 10,
            "condition_json": {"field": "vol_ratio", "op": "gte", "value": 2},
            "category": "volume",
        },
    )
    assert created.status_code == 201
    assert created.json()["item"]["rule_code"] == "CUSTOM_VOL"

    listed = client.get("/api/scoring/rules").json()
    assert listed["ok"] is True
    assert any(i["rule_code"] == "CUSTOM_VOL" for i in listed["items"])
