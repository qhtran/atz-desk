"""User Filter Resolver: đọc user_filter_configs + composite_rules từ SQLite (read-only). Không có -> mặc định."""
from __future__ import annotations

import json
import logging
import sqlite3
import time

from filter_runner.log import ERR_SYS_SQLITE, log


class UserFilterResolver:
    def __init__(self, sqlite_path: str, defaults: list[dict], default_user: str, ttl: float, clock=time.monotonic):
        self.path, self.defaults, self.default_user = sqlite_path, defaults, default_user
        self.ttl, self.clock = ttl, clock
        self._cache: dict[str, list[dict]] | None = None
        self._loaded = 0.0

    def _default_items(self) -> list[dict]:
        return [{"kind": "filter", "name": d["filter"], "params": d.get("params") or {}} for d in self.defaults]

    def _read(self) -> dict[str, list[dict]]:
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, timeout=5)
        try:
            users = [str(r[0]) for r in conn.execute("SELECT id FROM users ORDER BY id")]
            configs: dict[str, list[dict]] = {}
            for uid, name, params in conn.execute(
                    "SELECT user_id, filter_name, parameters FROM user_filter_configs WHERE enabled = 1 ORDER BY thu_tu, id"):
                configs.setdefault(str(uid), []).append(
                    {"kind": "filter", "name": name, "params": json.loads(params or "{}")})
            for owner, name, definition in conn.execute("SELECT owner, name, definition FROM composite_rules ORDER BY id"):
                configs.setdefault(str(owner), []).append(
                    {"kind": "composite", "name": name, "definition": json.loads(definition or "{}")})
        finally:
            conn.close()
        result = {uid: configs.get(uid) or self._default_items() for uid in users}
        for uid, items in configs.items():   # composite có owner không phải user id số
            result.setdefault(uid, items)
        return result or {self.default_user: self._default_items()}

    def plans(self) -> dict[str, list[dict]]:
        if self._cache is None or self.clock() - self._loaded >= self.ttl:
            try:
                self._cache = self._read()
                self._loaded = self.clock()
                log("RESOLVE", f"users={len(self._cache)} items={sum(len(v) for v in self._cache.values())}")
            except Exception as error:  # noqa: BLE001 - SQLite khoá/thiếu: giữ cache cũ hoặc mặc định
                log("RESOLVE", f"sqlite read failed: {type(error).__name__}: {error}", logging.ERROR,
                    error_code=ERR_SYS_SQLITE)
                if self._cache is None:
                    self._cache = {self.default_user: self._default_items()}
                self._loaded = self.clock()
        return self._cache
