"""Priceboard debug overlay config API."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from backend import debug_ui


def test_public_config_disabled_without_yaml(monkeypatch, tmp_path: Path):
    missing = tmp_path / "nope.yaml"
    monkeypatch.setenv("DEBUG_OVERLAY_CONFIG", str(missing))
    monkeypatch.delenv("PB_DEBUG_UI", raising=False)
    cfg = debug_ui.load_priceboard_debug_config()
    assert cfg["enabled"] is False
    assert cfg["storageKey"] == "pb-dbg-on"


def test_load_priceboard_surface(tmp_path: Path, monkeypatch):
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "debug_overlay": {
                    "enabled": True,
                    "priceboard_storage_key": "pb-dbg-on",
                    "surfaces": {"priceboard": {"enabled": True, "catalog": "ui_catalog.json"}},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEBUG_OVERLAY_CONFIG", str(path))
    monkeypatch.delenv("PB_DEBUG_UI", raising=False)
    cfg = debug_ui.load_priceboard_debug_config()
    assert cfg["enabled"] is True
    assert cfg["catalogUrl"] == "/static/ui_catalog.json"
    assert cfg["inspect"] is True


def test_pb_debug_ui_env_override(tmp_path: Path, monkeypatch):
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        yaml.safe_dump({"debug_overlay": {"enabled": True, "surfaces": {"priceboard": {"enabled": True}}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEBUG_OVERLAY_CONFIG", str(path))
    monkeypatch.setenv("PB_DEBUG_UI", "0")
    cfg = debug_ui.load_priceboard_debug_config()
    assert cfg["enabled"] is False


def test_api_debug_ui_config_route(monkeypatch, tmp_path: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        yaml.safe_dump({"debug_overlay": {"enabled": True, "surfaces": {"priceboard": {"enabled": True}}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEBUG_OVERLAY_CONFIG", str(path))
    monkeypatch.delenv("PB_DEBUG_UI", raising=False)
    r = client.get("/api/debug-ui/config")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert body["storageKey"] == "pb-dbg-on"
