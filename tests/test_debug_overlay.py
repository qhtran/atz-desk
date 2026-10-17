"""Lớp debug overlay: config, gate groups, sanitize id."""

from __future__ import annotations

from pathlib import Path

from ui.debug_overlay import load_debug_config, sanitize_dbg_id, user_may_use_debug


def test_sanitize_dbg_id() -> None:
    assert sanitize_dbg_id("DBG-RT-BOARD") == "DBG-RT-BOARD"
    assert sanitize_dbg_id("dbg_nav_1") == "dbg_nav_1"
    assert sanitize_dbg_id("<script>") == ""
    assert sanitize_dbg_id("a b") == ""
    assert sanitize_dbg_id("") == ""


def test_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_debug_config(tmp_path / "missing.yaml")
    assert config["enabled"] is False
    assert config["allow_local"] is False
    assert config["allowed_groups"] == []


def test_config_loads(tmp_path: Path) -> None:
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        "debug_overlay:\n"
        "  enabled: true\n"
        "  allow_local: true\n"
        "  allowed_groups: [admin, VIP]\n"
        "  storage_key: 'bad key!'\n",
        encoding="utf-8",
    )
    config = load_debug_config(path)
    assert config["enabled"] is True
    assert config["allow_local"] is True
    assert config["allowed_groups"] == ["admin", "VIP"]
    assert config["storage_key"] == "atz-dbg-on"  # invalid key → fallback


def test_gate_local_and_groups() -> None:
    cfg = {
        "enabled": True,
        "allow_local": True,
        "allowed_groups": ["admin", "authentik Admins"],
        "storage_key": "atz-dbg-on",
    }
    assert user_may_use_debug(None, cfg) is True
    assert user_may_use_debug({"groups": ["members"]}, cfg) is False
    assert user_may_use_debug({"groups": ["Admin"]}, cfg) is True
    assert user_may_use_debug({"groups": ["authentik Admins"]}, cfg) is True

    cfg_off = {**cfg, "enabled": False}
    assert user_may_use_debug(None, cfg_off) is False
    assert user_may_use_debug({"groups": ["admin"]}, cfg_off) is False

    cfg_no_local = {**cfg, "allow_local": False}
    assert user_may_use_debug(None, cfg_no_local) is False
