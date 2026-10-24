"""Lớp debug overlay: config, gate groups, sanitize id, table legend."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ui.debug_overlay import (
    compose_dbg_ref,
    extract_row_keys,
    load_debug_config,
    sanitize_dbg_id,
    sanitize_token,
    table_legend_html,
    user_may_use_debug,
)


def test_sanitize_dbg_id() -> None:
    assert sanitize_dbg_id("DBG-RT-BOARD") == "DBG-RT-BOARD"
    assert sanitize_dbg_id("dbg_nav_1") == "dbg_nav_1"
    assert sanitize_dbg_id("<script>") == ""
    assert sanitize_dbg_id("a b") == ""
    assert sanitize_dbg_id("") == ""


def test_sanitize_token_and_compose() -> None:
    assert sanitize_token("Giá") == "Giá"
    assert sanitize_token("%") == "x"
    assert sanitize_token("%", fallback="pct") == "pct"
    assert compose_dbg_ref("rt_board", col="Giá") == "atz-dbg:rt_board.col.Giá"
    assert compose_dbg_ref("rt_board", row="FPT") == "atz-dbg:rt_board.row.FPT"
    assert compose_dbg_ref("rt_board", row="FPT", col="Giá") == "atz-dbg:rt_board.cell.FPT.Giá"


def test_extract_row_keys() -> None:
    frame = pd.DataFrame({"Mã": ["fpt", "VIC", "FPT"], "Giá": [1, 2, 3]})
    assert extract_row_keys(frame, max_rows=10) == ["FPT", "VIC"]


def test_table_legend_html_escapes() -> None:
    html = table_legend_html("rt_board", ["Giá", "<x>"], ["FPT"])
    assert "atz-dbg:rt_board.col.Giá" in html
    assert "<x>" not in html
    assert "&lt;x&gt;" in html
    assert 'data-atz-dbg-pick="row:FPT"' in html


def test_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_debug_config(tmp_path / "missing.yaml")
    assert config["enabled"] is False
    assert config["table_deep"] is False
    assert config["allow_local"] is False
    assert config["allowed_groups"] == []


def test_config_loads_and_env_kill(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        "debug_overlay:\n"
        "  enabled: true\n"
        "  table_deep: true\n"
        "  allow_local: true\n"
        "  allowed_groups: [admin, VIP]\n"
        "  storage_key: 'bad key!'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ATZ_DEBUG_OVERLAY", raising=False)
    monkeypatch.delenv("ATZ_DEBUG_TABLE_DEEP", raising=False)
    config = load_debug_config(path)
    assert config["enabled"] is True
    assert config["table_deep"] is True
    assert config["allowed_groups"] == ["admin", "VIP"]
    assert config["storage_key"] == "atz-dbg-on"

    monkeypatch.setenv("ATZ_DEBUG_OVERLAY", "0")
    assert load_debug_config(path)["enabled"] is False
    monkeypatch.setenv("ATZ_DEBUG_TABLE_DEEP", "0")
    assert load_debug_config(path)["table_deep"] is False


def test_gate_local_and_groups() -> None:
    cfg = {
        "enabled": True,
        "table_deep": True,
        "allow_local": True,
        "allowed_groups": ["admin", "authentik Admins"],
        "storage_key": "atz-dbg-on",
        "atz_inspect_enabled": False,
        "require_admin_groups": True,
    }
    assert user_may_use_debug(None, cfg) is True
    assert user_may_use_debug({"groups": ["members"]}, cfg) is False
    assert user_may_use_debug({"groups": ["Admin"]}, cfg) is True
    assert user_may_use_debug({"groups": ["authentik Admins"]}, cfg) is True
    assert user_may_use_debug({"username": "u", "groups": []}, cfg) is False

    cfg_off = {**cfg, "enabled": False}
    assert user_may_use_debug(None, cfg_off) is False
    assert user_may_use_debug({"groups": ["admin"]}, cfg_off) is False

    cfg_no_local = {**cfg, "allow_local": False}
    assert user_may_use_debug(None, cfg_no_local) is False

    cfg_atz_open = {
        **cfg,
        "atz_inspect_enabled": True,
        "require_admin_groups": False,
    }
    assert user_may_use_debug({"username": "u", "groups": []}, cfg_atz_open) is True
    assert user_may_use_debug({"groups": ["members"]}, cfg_atz_open) is True


def test_config_atz_surface_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "debug_overlay.yaml"
    path.write_text(
        "debug_overlay:\n"
        "  enabled: true\n"
        "  surfaces:\n"
        "    atz:\n"
        "      enabled: true\n"
        "      inspect: true\n",
        encoding="utf-8",
    )
    cfg = load_debug_config(path)
    assert cfg["atz_inspect_enabled"] is True
    assert user_may_use_debug({"username": "u", "groups": []}, cfg) is True
