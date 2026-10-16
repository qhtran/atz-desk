"""Đường dẫn gốc repo — ổn định khi code chuyển vào src/atz/."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_MARKER = Path("config") / "ingestion.yaml"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Thư mục chứa `config/ingestion.yaml` (cạnh `data/`, Dockerfile WORKDIR)."""
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / _MARKER).is_file():
            return candidate
    raise RuntimeError(f"Không tìm thấy repo root (thiếu {_MARKER})")
