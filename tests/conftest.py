"""DB tạm cho mọi test repository. Không đụng data/signals.db."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from storage.db import connect, migrate


@pytest.fixture
def db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "signals.db")
    migrate(conn)
    yield conn
    conn.close()
