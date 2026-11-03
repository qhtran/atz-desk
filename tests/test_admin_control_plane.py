"""Admin Control Panel B3 — RBAC + overlay roundtrip."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.admin_config_store import get_control_plane, put_control_plane, sanitize_stream_patch
from backend.main import app

ADMIN_H = {
    "X-Authentik-Username": "boss",
    "X-Authentik-Groups": "admin",
}
USER_H = {
    "X-Authentik-Username": "hoa",
    "X-Authentik-Groups": "members",
}


def test_sanitize_stream_patch_whitelist():
    out = sanitize_stream_patch(
        {"rsi": {"oversold": 25, "evil": 1}, "channel": "hack", "cooldown_sec": 60}
    )
    assert out["cooldown_sec"] == 60
    assert out["rsi"] == {"oversold": 25.0}
    assert "channel" not in out
    assert "evil" not in out.get("rsi", {})


def test_put_get_overlay_roundtrip(tmp_path: Path):
    path = tmp_path / "admin_runtime_config.json"
    put_control_plane(
        {"stream_alerts": {"rsi": {"oversold": 28}, "cooldown_sec": 90}},
        overlay_path=path,
    )
    data = get_control_plane(path)
    assert data["has_overlay"] is True
    assert data["stream_alerts"]["rsi"]["oversold"] == 28.0
    assert data["stream_alerts"]["cooldown_sec"] == 90
    # base fields vẫn còn
    assert data["stream_alerts"]["rsi"]["overbought"] == 70


def test_admin_get_requires_auth():
    client = TestClient(app)
    assert client.get("/api/admin/control-plane").status_code == 401


def test_admin_get_forbids_non_admin():
    client = TestClient(app)
    assert client.get("/api/admin/control-plane", headers=USER_H).status_code == 403


def test_admin_get_ok_for_admin():
    client = TestClient(app)
    res = client.get("/api/admin/control-plane", headers=ADMIN_H)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "rsi" in body["stream_alerts"]
    assert "stop_loss_pct" in body["risk"]


def test_admin_put_and_reload(tmp_path: Path, monkeypatch):
    path = tmp_path / "admin_runtime_config.json"
    monkeypatch.setenv("ADMIN_RUNTIME_CONFIG", str(path))
    # re-import path binding — put uses DEFAULT_OVERLAY at call time via env in store
    import backend.admin_config_store as store

    monkeypatch.setattr(store, "DEFAULT_OVERLAY", path)

    client = TestClient(app)
    res = client.put(
        "/api/admin/control-plane",
        headers=ADMIN_H,
        json={
            "stream_alerts": {"rsi": {"oversold": 22}, "volume_spike": {"mult": 2.5}},
            "risk": {"stop_loss_pct": 5, "max_positions": 10},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["stream_alerts"]["rsi"]["oversold"] == 22.0
    assert body["stream_alerts"]["volume_spike"]["mult"] == 2.5
    assert body["risk"]["stop_loss_pct"] == 5.0
    assert body["risk"]["max_positions"] == 10
    assert path.is_file()
