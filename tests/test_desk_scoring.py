"""Scoring Matrix engine + /api/scoring endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.desk_scoring_engine import (
    DEFAULT_SEED_RULES,
    decision_from_score_pct,
    decision_label_vi,
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
    assert decision_label_vi("STRONG_BUY") == "Mua mạnh"
    assert decision_label_vi("ACCUMULATE") == "Tích lũy"
    assert decision_label_vi("HOLD") == "Giữ"
    assert decision_label_vi("TRIM") == "Giảm"
    assert decision_label_vi("SELL") == "Bán"


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


def test_presets_catalog_and_profile_evaluate(monkeypatch, tmp_path: Path):
    from backend.desk_scoring_presets import clear_presets_cache, get_preset_rules, list_presets

    clear_presets_cache()
    catalog = list_presets()
    assert catalog["default_profile"] == "default"
    ids = {i["id"] for i in catalog["items"]}
    assert {"default", "momentum", "mean_reversion", "trend_following"} <= ids

    pid, rules = get_preset_rules("momentum")
    assert pid == "momentum"
    assert sum(r["weight"] for r in rules) == pytest.approx(100)
    assert all(r["condition_json"]["field"] != "rsi" for r in rules)

    tf_id, tf_rules = get_preset_rules("trend_following")
    assert tf_id == "trend_following"
    assert sum(r["weight"] for r in tf_rules) == pytest.approx(100)
    assert len(tf_rules) == 4

    path = tmp_path / "api_scoring.db"
    import backend.desk_scoring_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_scoring_store(path)
    client = TestClient(app)

    presets = client.get("/api/scoring/presets").json()
    assert presets["ok"] is True
    assert len(presets["items"]) >= 4
    assert any(i["id"] == "trend_following" for i in presets["items"])

    # default profile: indicators tuned so all 5 rules hit (price_vs_ma20 = ratio)
    res = client.post(
        "/api/scoring/evaluate",
        json={
            "symbol": "FPT",
            "profile": "default",
            "indicators": {
                "rsi": 25,
                "price_vs_ma20": 1.05,
                "macd_hist": 0.2,
                "vol_ratio": 2.5,
                "change_pct": 1.2,
            },
            "persist": False,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["profile"] == "default"
    assert body["score_pct"] == pytest.approx(100)
    assert body["decision"] == "STRONG_BUY"
    assert body["decision_label"] == "Mua mạnh"
    assert len(body["breakdown"]) == 5

    # mean_reversion: oversold + below MA
    mr = client.post(
        "/api/scoring/evaluate",
        json={
            "symbol": "HPG",
            "profile": "mean_reversion",
            "indicators": {
                "rsi": 28,
                "price_vs_ma20": 0.97,
                "macd_hist": -0.2,
                "vol_ratio": 1.2,
                "change_pct": -1,
            },
            "persist": False,
        },
    )
    assert mr.status_code == 200
    assert mr.json()["profile"] == "mean_reversion"
    assert mr.json()["score_pct"] == pytest.approx(100)

    tf = client.post(
        "/api/scoring/evaluate",
        json={
            "symbol": "VCB",
            "profile": "trend_following",
            "indicators": {
                "rsi": 55,
                "price_vs_ma20": 1.04,
                "macd_hist": 0.15,
                "vol_ratio": 1.3,
                "change_pct": 0.5,
            },
            "persist": False,
        },
    )
    assert tf.status_code == 200
    assert tf.json()["profile"] == "trend_following"
    assert tf.json()["score_pct"] == pytest.approx(100)
    assert len(tf.json()["breakdown"]) == 4

    bad = client.post(
        "/api/scoring/evaluate",
        json={"symbol": "AAA", "profile": "nope", "indicators": {}, "persist": False},
    )
    assert bad.status_code == 400

    # alias path still works (default profile)
    alias = client.post(
        "/api/evaluate",
        json={"symbol": "SSI", "indicators": {"rsi": 10}, "persist": False},
    )
    assert alias.status_code == 200
    assert alias.json()["profile"] == "default"

    # rules write requires auth — SQLite path isolated from presets
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

    # evaluate still uses YAML preset, not CUSTOM_VOL from DB
    again = client.post(
        "/api/scoring/evaluate",
        json={
            "symbol": "FPT",
            "profile": "momentum",
            "indicators": {
                "price_vs_ma20": 1.03,
                "vol_ratio": 3.0,
                "macd_hist": 0.1,
                "change_pct": 1.5,
            },
            "persist": False,
        },
    )
    assert again.status_code == 200
    codes = {b["rule_code"] for b in again.json()["breakdown"]}
    assert "CUSTOM_VOL" not in codes
    assert "MOM_VOL" in codes
