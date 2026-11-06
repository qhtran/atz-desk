"""Admin Control Panel B3 — RBAC + overlay roundtrip."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.admin_config_store import (
    flatten_screening_filters,
    get_control_plane,
    inflate_flat_screening_filters,
    normalize_control_plane_body,
    put_control_plane,
    sanitize_stream_patch,
)
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


def test_inflate_flat_screening_filters():
    nested = inflate_flat_screening_filters(
        {
            "rsi_oversold": 28,
            "rsi_overbought": 72,
            "volume_spike_mult": 2.5,
            "ma_fast_period": 8,
            "ma_slow_period": 21,
        }
    )
    assert nested["rsi"] == {"oversold": 28, "overbought": 72}
    assert nested["volume_spike"] == {"mult": 2.5}
    assert nested["ma"] == {"fast": 8, "slow": 21}


def test_normalize_merges_flat_and_nested():
    body = normalize_control_plane_body(
        {
            "stream_alerts": {"rsi": {"length": 14}},
            "rsi_oversold": 31,
            "volume_spike_mult": 2.5,
        }
    )
    assert body["stream_alerts"]["rsi"]["length"] == 14
    assert body["stream_alerts"]["rsi"]["oversold"] == 31
    assert body["stream_alerts"]["volume_spike"]["mult"] == 2.5


def test_flatten_screening_filters_roundtrip():
    flat = flatten_screening_filters(
        {"rsi": {"length": 14, "oversold": 30, "overbought": 70}, "ma": {"fast": 10, "slow": 20}, "volume_spike": {"mult": 2.5, "lookback": 20}}
    )
    assert flat["rsi_oversold"] == 30
    assert flat["volume_spike_mult"] == 2.5
    assert flat["ma_fast_period"] == 10


def test_admin_put_and_reload(tmp_path: Path, monkeypatch):
    path = tmp_path / "admin_runtime_config.json"
    monkeypatch.setenv("ADMIN_RUNTIME_CONFIG", str(path))
    # re-import path binding — put uses DEFAULT_OVERLAY at call time via env in store
    import backend.admin_config_store as store

    monkeypatch.setattr(store, "DEFAULT_OVERLAY", path)

    published: list[dict] = []

    async def _fake_publish(stream_alerts=None, **_kwargs):
        published.append(stream_alerts or {})
        return True

    monkeypatch.setattr("backend.routers.admin.publish_config_reload", _fake_publish)

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
    assert body["screening_filters"]["rsi_oversold"] == 22.0
    assert body["screening_filters"]["volume_spike_mult"] == 2.5
    assert body["risk"]["stop_loss_pct"] == 5.0
    assert body["risk"]["max_positions"] == 10
    assert body["config_reload_channel"] == "admin:config-reload"
    assert path.is_file()
    assert published and published[0]["rsi"]["oversold"] == 22.0


def test_admin_post_flat_keys(tmp_path: Path, monkeypatch):
    path = tmp_path / "admin_runtime_config.json"
    import backend.admin_config_store as store

    monkeypatch.setattr(store, "DEFAULT_OVERLAY", path)

    async def _fake_publish(stream_alerts=None, **_kwargs):
        return True

    monkeypatch.setattr("backend.routers.admin.publish_config_reload", _fake_publish)

    client = TestClient(app)
    res = client.post(
        "/api/admin/control-plane",
        headers=ADMIN_H,
        json={
            "rsi_oversold": 27,
            "rsi_overbought": 73,
            "volume_spike_mult": 2.5,
            "ma_fast_period": 9,
            "ma_slow_period": 26,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["stream_alerts"]["rsi"]["oversold"] == 27.0
    assert body["stream_alerts"]["rsi"]["overbought"] == 73.0
    assert body["stream_alerts"]["volume_spike"]["mult"] == 2.5
    assert body["stream_alerts"]["ma"]["fast"] == 9
    assert body["stream_alerts"]["ma"]["slow"] == 26
    assert body["screening_filters"]["ma_fast_period"] == 9


def test_admin_min_traded_value_overlay(tmp_path: Path):
    path = tmp_path / "admin_runtime_config.json"
    put_control_plane(
        {"min_traded_value": {"HOSE": 4_000_000_000, "HNX": "nope", "UPCOM": 1_000_000_000}},
        overlay_path=path,
    )
    data = get_control_plane(path)
    assert data["min_traded_value"]["HOSE"] == 4_000_000_000
    assert data["min_traded_value"]["HNX"] == 1_000_000_000
    assert data["min_traded_value"]["UPCOM"] == 1_000_000_000
