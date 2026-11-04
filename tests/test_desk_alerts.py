"""Desk Telegram Alerts Phase 1–2: SQLite store + /api/alerts CRUD + GT/LT biên."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.desk_alerts_store import (
    condition_met,
    create_alert_config,
    deactivate_alert_config,
    init_desk_alerts_store,
    latest_history_for_config,
    list_alert_configs,
    record_alert_history,
)
from backend.main import app


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "desk_alerts.db"
    init_desk_alerts_store(path)
    return path


def test_condition_met_gt_lt_boundaries():
    assert condition_met("GT", 10.1, 10.0) is True
    assert condition_met("GT", 10.0, 10.0) is False
    assert condition_met("GT", 9.9, 10.0) is False
    assert condition_met("LT", 9.9, 10.0) is True
    assert condition_met("LT", 10.0, 10.0) is False
    assert condition_met("LT", 10.1, 10.0) is False
    assert condition_met("gt", 11, 10) is True  # case-insensitive
    assert condition_met("XX", 11, 10) is False


def test_store_create_list_deactivate(db: Path):
    a = create_alert_config("hoa", symbol="fpt", condition="GT", target_value=100.5, db_path=db)
    assert a["symbol"] == "FPT"
    assert a["condition"] == "GT"
    assert a["target_value"] == 100.5
    assert a["is_active"] is True

    b = create_alert_config("hoa", symbol="VNM", condition="LT", target_value=50, db_path=db)
    items = list_alert_configs("hoa", active_only=True, db_path=db)
    assert {i["id"] for i in items} == {a["id"], b["id"]}

    # other user isolated
    assert list_alert_configs("other", db_path=db) == []

    gone = deactivate_alert_config("hoa", a["id"], db_path=db)
    assert gone is not None and gone["is_active"] is False
    active = list_alert_configs("hoa", active_only=True, db_path=db)
    assert [i["id"] for i in active] == [b["id"]]
    assert deactivate_alert_config("hoa", a["id"], db_path=db) is None  # already off
    assert deactivate_alert_config("other", b["id"], db_path=db) is None  # wrong user


def test_store_rejects_bad_inputs(db: Path):
    with pytest.raises(ValueError, match="condition"):
        create_alert_config("hoa", symbol="FPT", condition="EQ", target_value=1, db_path=db)
    with pytest.raises(ValueError, match="target_value"):
        create_alert_config("hoa", symbol="FPT", condition="GT", target_value=0, db_path=db)
    with pytest.raises(ValueError, match="symbol"):
        create_alert_config("hoa", symbol="  ", condition="GT", target_value=1, db_path=db)


def test_alert_history_roundtrip(db: Path):
    cfg = create_alert_config("hoa", symbol="HPG", condition="GT", target_value=30, db_path=db)
    assert condition_met(cfg["condition"], 30.5, cfg["target_value"]) is True
    hist = record_alert_history(cfg["id"], 30.5, db_path=db)
    assert hist["last_price"] == 30.5
    latest = latest_history_for_config(cfg["id"], db_path=db)
    assert latest is not None and latest["id"] == hist["id"]


def test_api_alerts_requires_auth(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_alerts.db"
    monkeypatch.setenv("DESK_ALERTS_DB_PATH", str(path))
    # re-import DEFAULT path is already bound — patch store DEFAULT_DB via monkeypatch on module
    import backend.desk_alerts_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_alerts_store(path)
    client = TestClient(app)
    assert client.get("/api/alerts").status_code == 401
    assert client.post("/api/alerts", json={"symbol": "FPT", "condition": "GT", "target_value": 1}).status_code == 401


def test_api_alerts_crud_flow(monkeypatch, tmp_path: Path):
    path = tmp_path / "api_alerts.db"
    import backend.desk_alerts_store as store

    monkeypatch.setattr(store, "DEFAULT_DB", path)
    init_desk_alerts_store(path)
    client = TestClient(app)
    headers = {
        "X-Authentik-Username": "hoa",
        "X-Authentik-Groups": "members",
    }

    res = client.post(
        "/api/alerts",
        headers=headers,
        json={"symbol": "fpt", "condition": "GT", "target_value": 95.5},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["ok"] is True
    item = body["item"]
    assert item["symbol"] == "FPT"
    assert item["condition"] == "GT"
    alert_id = item["id"]

    listed = client.get("/api/alerts", headers=headers).json()
    assert listed["ok"] is True
    assert any(i["id"] == alert_id for i in listed["items"])

    # validation biên
    bad = client.post(
        "/api/alerts",
        headers=headers,
        json={"symbol": "FPT", "condition": "EQ", "target_value": 1},
    )
    assert bad.status_code == 422

    deleted = client.delete(f"/api/alerts/{alert_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deactivated"] == alert_id
    assert deleted.json()["item"]["is_active"] is False

    listed2 = client.get("/api/alerts", headers=headers).json()
    assert all(i["id"] != alert_id for i in listed2["items"])

    assert client.delete(f"/api/alerts/{alert_id}", headers=headers).status_code == 404
