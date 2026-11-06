"""Auth rate limit for bypassed /api/auth/login|logout."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import auth_rate_limit as rl
from backend.desk_session import COOKIE_NAME
from backend.main import app


@pytest.fixture()
def desk_env(monkeypatch):
    monkeypatch.setenv("DESK_SESSION_AUTH", "1")
    monkeypatch.setenv("DESK_SESSION_SECRET", "test-secret-desk-session-please-change")
    monkeypatch.setenv("DESK_SESSION_SECURE", "0")
    monkeypatch.setenv("AUTHENTIK_FLOW_URL", "https://auth.example/api/v3/flows/executor/x/")
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT", "3")
    monkeypatch.setenv("AUTH_LOGIN_RATE_WINDOW_SEC", "600")
    monkeypatch.setenv("AUTH_LOGOUT_RATE_LIMIT", "5")
    monkeypatch.setenv("AUTH_LOGOUT_RATE_WINDOW_SEC", "60")
    rl.reset_for_tests()
    yield
    rl.reset_for_tests()


def test_sliding_window_blocks(desk_env):
    assert rl.check_rate_limit("t:a", limit=2, window_sec=60)[0] is True
    assert rl.check_rate_limit("t:a", limit=2, window_sec=60)[0] is True
    ok, retry = rl.check_rate_limit("t:a", limit=2, window_sec=60)
    assert ok is False
    assert retry >= 1


def test_login_rate_limit_http(desk_env, monkeypatch):
    from backend.authentik_ropc import RopcAuthError

    def boom(*args, **kwargs):
        raise RopcAuthError("invalid")

    monkeypatch.setattr("backend.main.password_grant", boom)
    # Re-import app bindings after rl reload — use current app
    client = TestClient(app)
    for _ in range(3):
        res = client.post("/api/auth/login", json={"username": "hoa", "password": "bad"})
        assert res.status_code == 401
    blocked = client.post("/api/auth/login", json={"username": "hoa", "password": "bad"})
    assert blocked.status_code == 429
    assert blocked.json()["detail"]
    assert "Retry-After" in blocked.headers


def test_logout_clears_and_hints_outpost(desk_env, monkeypatch):
    def fake_grant(username, password, **kwargs):
        return {
            "username": "hoa",
            "email": "hoa@example.com",
            "name": "Hoa",
            "uid": "u1",
            "groups": ["members"],
        }

    monkeypatch.setattr("backend.main.password_grant", fake_grant)
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "hoa", "password": "secret"})
    assert login.status_code == 200
    assert COOKIE_NAME in client.cookies
    out = client.post("/api/auth/logout")
    assert out.status_code == 200
    body = out.json()
    assert body["local_logout"] is True
    assert body["desk_cookie_cleared"] is True
    # desk_session → no outpost required
    assert body.get("auth_source") == "desk_session"
    assert body.get("outpost_sign_out") is None
