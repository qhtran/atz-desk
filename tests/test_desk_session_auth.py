"""DEV Desk Session + ROPC login (mocked Authentik)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.desk_session import COOKIE_NAME, issue_session_value, verify_session_value
from backend.identity import resolve_me
from backend.main import app


@pytest.fixture()
def desk_env(monkeypatch):
    monkeypatch.setenv("DESK_SESSION_AUTH", "1")
    monkeypatch.setenv("DESK_SESSION_SECRET", "test-secret-desk-session-please-change")
    monkeypatch.setenv("DESK_SESSION_SECURE", "0")
    monkeypatch.setenv(
        "AUTHENTIK_FLOW_URL",
        "https://auth.example/api/v3/flows/executor/desk-ropc-authentication/",
    )


def test_issue_and_verify_session(desk_env):
    token = issue_session_value(username="hoa", email="hoa@x", groups=["members"])
    me = verify_session_value(token)
    assert me is not None
    assert me["username"] == "hoa"
    assert me["groups"] == ["members"]
    assert me["source"] == "desk_session"


def test_resolve_me_prefers_forward_auth(desk_env):
    token = issue_session_value(username="cookie-user", groups=[])
    me = resolve_me(
        {"x-authentik-username": "header-user", "x-authentik-groups": "admin"},
        desk_cookie=token,
    )
    assert me is not None
    assert me["username"] == "header-user"
    assert me["source"] == "forward_auth"


def test_resolve_me_falls_back_to_cookie(desk_env):
    token = issue_session_value(username="cookie-user", groups=["vip"])
    me = resolve_me({}, desk_cookie=token)
    assert me is not None
    assert me["username"] == "cookie-user"
    assert me["groups"] == ["vip"]


def test_account_me_with_desk_cookie(desk_env):
    token = issue_session_value(username="boss", groups=["admin"])
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, token)
    res = client.get("/api/account/me")
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["is_admin"] is True
    assert data["auth_source"] == "desk_session"


def test_login_ropc_success(desk_env, monkeypatch):
    def fake_grant(username, password, **kwargs):
        assert username == "hoa"
        assert password == "secret"
        return {
            "username": "hoa",
            "email": "hoa@example.com",
            "name": "Hoa",
            "uid": "u1",
            "groups": ["members"],
        }

    monkeypatch.setattr("backend.main.password_grant", fake_grant)
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "hoa", "password": "secret"})
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["authenticated"] is True
    assert body["user"]["username"] == "hoa"
    assert COOKIE_NAME in res.cookies


def test_login_ropc_bad_password(desk_env, monkeypatch):
    from backend.authentik_ropc import RopcAuthError

    def boom(*args, **kwargs):
        raise RopcAuthError("invalid")

    monkeypatch.setattr("backend.main.password_grant", boom)
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "hoa", "password": "wrong"})
    assert res.status_code == 401
    assert "Sai tài khoản" in res.json()["detail"]


def test_login_disabled_without_env(monkeypatch):
    monkeypatch.delenv("DESK_SESSION_AUTH", raising=False)
    monkeypatch.delenv("DESK_SESSION_SECRET", raising=False)
    monkeypatch.delenv("AUTHENTIK_FLOW_URL", raising=False)
    monkeypatch.delenv("AUTHENTIK_BASE_URL", raising=False)
    monkeypatch.delenv("AUTHENTIK_TOKEN_URL", raising=False)
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "hoa", "password": "x"})
    assert res.status_code == 503


def test_flow_password_grant_success(desk_env, monkeypatch):
    from backend import authentik_ropc as mod

    class FakeResp:
        def __init__(self, status_code=200, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}

        def json(self):
            return self._payload

    class FakeSession:
        def get(self, url, **kwargs):
            if "users/me" in url:
                return FakeResp(
                    payload={
                        "user": {
                            "username": "hoa",
                            "email": "hoa@example.com",
                            "name": "Hoa",
                            "uid": "u1",
                            "groups": [{"name": "members"}],
                        }
                    }
                )
            return FakeResp(payload={"component": "ak-stage-identification"})

        def post(self, url, **kwargs):
            body = kwargs.get("json") or {}
            if body.get("component") == "ak-stage-identification":
                return FakeResp(
                    payload={"component": "ak-stage-user-login", "pending_user": "hoa"}
                )
            if body.get("component") == "ak-stage-user-login":
                return FakeResp(
                    payload={"component": "xak-flow-redirect", "to": "/", "final_redirect": True}
                )
            return FakeResp(payload={"component": "ak-stage-identification"})

    monkeypatch.setattr(mod.requests, "Session", FakeSession)
    profile = mod.password_grant("hoa", "secret")
    assert profile["username"] == "hoa"
    assert profile["email"] == "hoa@example.com"
    assert profile["groups"] == ["members"]


def test_flow_password_grant_bad_password(desk_env, monkeypatch):
    from backend import authentik_ropc as mod

    class FakeResp:
        def __init__(self, status_code=200, payload=None, headers=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}

        def json(self):
            return self._payload

    class FakeSession:
        def get(self, url, **kwargs):
            return FakeResp(payload={"component": "ak-stage-identification"})

        def post(self, url, **kwargs):
            return FakeResp(
                payload={
                    "component": "ak-stage-identification",
                    "response_errors": {
                        "non_field_errors": [{"string": "Failed to authenticate.", "code": "invalid"}]
                    },
                }
            )

    monkeypatch.setattr(mod.requests, "Session", FakeSession)
    with pytest.raises(mod.RopcAuthError, match="invalid credentials"):
        mod.password_grant("hoa", "wrong")
