"""Xuất và nhập JSON cấu hình của một user."""

from __future__ import annotations

import sqlite3
from typing import Any

from filters import load_registry
from storage.repository import (
    add_composite_rule,
    delete_composite_rules,
    delete_filter_configs,
    get_user,
    list_composite_rules,
    list_filter_configs,
    save_filter_config,
    set_user_settings,
)

EXPORT_VERSION = 1


def export_user(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    user = get_user(conn, user_id)
    if user is None:
        raise LookupError("không có user")
    return {
        "version": EXPORT_VERSION,
        "username": user["username"],
        "email": user["email_nhan_thong_bao"],
        "settings": user["cai_dat_chung"],
        "filters": [
            {
                "filter_name": row["filter_name"],
                "parameters": row["parameters"],
                "enabled": bool(row["enabled"]),
                "thu_tu": row["thu_tu"],
            }
            for row in list_filter_configs(conn, user_id)
        ],
        "composites": [
            {"name": row["name"], "definition": row["definition"], "mo_ta": row["mo_ta"] or ""}
            for row in list_composite_rules(conn, str(user_id))
        ],
    }


def import_user(conn: sqlite3.Connection, user_id: int, payload: dict[str, Any], replace: bool = False) -> None:
    """Ghi vào đúng user_id. Username trong file không đổi user đang nhập."""
    if payload.get("version") != EXPORT_VERSION:
        raise ValueError("version không hỗ trợ")
    known = set(load_registry())
    filters = payload.get("filters") or []
    for item in filters:
        name = item.get("filter_name")
        if name not in known:
            raise ValueError(f"không có filter {name}")
    if get_user(conn, user_id) is None:
        raise LookupError("không có user")
    if replace:
        delete_filter_configs(conn, user_id)
        delete_composite_rules(conn, str(user_id))
    if "settings" in payload or "email" in payload:
        current = get_user(conn, user_id)
        email = payload["email"] if "email" in payload else current["email_nhan_thong_bao"]
        settings = payload["settings"] if "settings" in payload else current["cai_dat_chung"]
        set_user_settings(conn, user_id, settings, email)
    for index, item in enumerate(filters):
        save_filter_config(
            conn,
            user_id,
            item["filter_name"],
            item.get("parameters") or {},
            bool(item.get("enabled", True)),
            int(item.get("thu_tu", index)),
        )
    for item in payload.get("composites") or []:
        add_composite_rule(
            conn,
            item["name"],
            str(user_id),
            item.get("definition") or {},
            item.get("mo_ta") or "",
        )
