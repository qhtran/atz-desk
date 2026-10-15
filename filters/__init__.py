"""Quét thư mục filters và đăng ký mọi module có FILTER + evaluate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SKIP = {"base"}


def load_registry(folder: Path | None = None) -> dict[str, ModuleType]:
    """Đọc các file .py trong folder. Không có danh sách filter viết cứng."""
    path = folder or Path(__file__).resolve().parent
    found: dict[str, ModuleType] = {}
    for file in sorted(path.glob("*.py")):
        if file.name.startswith("_") or file.stem in _SKIP:
            continue
        spec = importlib.util.spec_from_file_location(f"filterplugin_{file.stem}", file)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        filt = getattr(module, "FILTER", None)
        if filt is None or not hasattr(module, "evaluate"):
            continue
        found[filt.name] = module
    return found
