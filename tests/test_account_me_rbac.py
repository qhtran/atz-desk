"""Desk /api/account/me — groups, roles, is_admin, login/logout URLs."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.account_config import load_account_config, safe_https_url
from backend.identity import is_admin_user, roles_for_user
from backend.main import app


def test_safe_https_url():
    assert safe_https_url("https://dev.atz.vn/") == "https://dev.atz.vn/"
    assert safe_https_url("http://evil") == ""
    assert safe_https_url("javascript:x") == ""


def test_is_admin_user_case_insensitive():
    assert is_admin_user(["admin"], ["admin"]) is True
    assert is_admin_user(["Admin"], ["admin"]) is True
    assert is_admin_user(["atz-admins"], ["admin", "atz-admins"]) is True
    assert is_admin_user(["members"], ["admin"]) is False
    assert is_admin_user([], ["admin"]) is False


def test_roles_for_user():
    assert roles_for_user(["members"], is_admin=False) == ["user", "members"]
    roles = roles_for_user(["admin", "vip"], is_admin=True)
    assert roles[0] == "user"
    assert "admin" in roles
    assert "vip" in roles


def test_load_repo_account_config():
    cfg = load_account_config()
    assert cfg["enabled"] is True
    assert cfg["login_url"].startswith("https://")
    assert cfg["logout_url"].startswith("https://")
    lowered = [g.lower() for g in cfg["admin_groups"]]
    assert "admin" in lowered
    assert "administrator" in lowered
    assert "authentik admins" in lowered


def test_load_account_config_tmp(tmp_path: Path):
    path = tmp_path / "account.yaml"
    path.write_text(
        "account:\n  enabled: true\n  login_url: 'https://dev.atz.vn/'\n"
        "  logout_url: 'javascript:x'\n  admin_groups: [ops]\n",
        encoding="utf-8",
    )
    cfg = load_account_config(path)
    assert cfg["login_url"] == "https://dev.atz.vn/"
    assert cfg["logout_url"] == ""
    assert cfg["admin_groups"] == ["ops"]


def test_account_me_unauthenticated():
    client = TestClient(app)
    res = client.get("/api/account/me")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["authenticated"] is False
    assert data["user"] is None
    assert data["is_admin"] is False
    assert data["groups"] == []
    assert data["roles"] == []
    assert "login_url" in data and "logout_url" in data


def test_account_me_user_not_admin():
    client = TestClient(app)
    res = client.get(
        "/api/account/me",
        headers={
            "X-Authentik-Username": "hoa",
            "X-Authentik-Name": "Hoa",
            "X-Authentik-Email": "hoa@example.com",
            "X-Authentik-Groups": "members|vip",
        },
    )
    data = res.json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "hoa"
    assert data["groups"] == ["members", "vip"]
    assert data["is_admin"] is False
    assert "user" in data["roles"]
    assert "admin" not in data["roles"] or data["roles"].count("admin") == 0


def test_account_me_admin_group():
    client = TestClient(app)
    res = client.get(
        "/api/account/me",
        headers={
            "X-Authentik-Username": "boss",
            "X-Authentik-Groups": "members|admin",
        },
    )
    data = res.json()
    assert data["authenticated"] is True
    assert data["is_admin"] is True
    assert "admin" in data["roles"]
    assert data["user"]["is_admin"] is True


def test_account_me_authentik_administrator_group():
    """Group tên Authentik ``Administrator`` map → is_admin qua account.yaml."""
    assert is_admin_user(["Administrator"], ["admin", "Administrator", "authentik Admins"]) is True
    client = TestClient(app)
    res = client.get(
        "/api/account/me",
        headers={
            "X-Authentik-Username": "atz-admin",
            "X-Authentik-Groups": "authentik Admins|Administrator",
        },
    )
    data = res.json()
    assert data["authenticated"] is True
    assert data["is_admin"] is True
    assert "admin" in data["roles"]


def test_is_admin_user_authentik_admin_aliases():
    cfg_groups = ["admin", "atz-admins", "Administrator", "authentik Admins"]
    assert is_admin_user(["Administrator"], cfg_groups) is True
    assert is_admin_user(["authentik Admins"], cfg_groups) is True
    assert is_admin_user(["members"], cfg_groups) is False


def test_healthz_smoke():
    client = TestClient(app)
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert "ok" in body
    assert "alert_clients" in body
