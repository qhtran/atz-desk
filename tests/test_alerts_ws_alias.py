"""Milestone 4 — /ws/alerts alias of /ws/stream/alerts."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.alerts_ws import register_alerts_ws_alias
from backend.websocket_manager import ConnectionManager
from backend.ws_alerts import register_alerts_ws


def _mini_app() -> FastAPI:
    app = FastAPI()
    mgr = ConnectionManager()
    register_alerts_ws(app, mgr)
    register_alerts_ws_alias(app, mgr)
    return app


@pytest.fixture()
def client():
    with TestClient(_mini_app()) as c:
        yield c


def test_ws_alerts_alias_hello(client: TestClient):
    with client.websocket_connect("/ws/alerts") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "hello"
        assert hello["channel"] == "alerts"
        assert hello["authenticated"] is False
        ws.send_text("ping")
        assert json.loads(ws.receive_text())["type"] == "pong"


def test_ws_stream_alerts_still_works(client: TestClient):
    with client.websocket_connect("/ws/stream/alerts") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "hello"
        assert hello["channel"] == "stream_alerts"


def test_ws_alerts_require_auth_rejects(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALERTS_WS_REQUIRE_AUTH", "1")
    with TestClient(_mini_app()) as client:
        with client.websocket_connect("/ws/alerts") as ws:
            first = json.loads(ws.receive_text())
            assert first.get("type") == "error"
            assert "auth" in str(first.get("detail", "")).lower()
