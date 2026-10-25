"""Capture call site or exception frame for structured logs."""

from __future__ import annotations

import inspect
import traceback
from typing import Any


def capture_origin(*, exc: BaseException | None = None, depth: int = 1) -> dict[str, Any]:
    """Return file, line, function, qualname for the fault site."""
    if exc is not None and exc.__traceback__ is not None:
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            finfo = frames[-1]
            return _from_tb(finfo)

    stack = inspect.stack()
    idx = 1 + max(depth, 0)
    if idx >= len(stack):
        idx = len(stack) - 1
    frame_info = stack[idx]
    qualname = frame_info.function
    try:
        loc = frame_info.frame.f_locals
        cls = loc.get("self")
        if cls is not None and hasattr(cls, "__class__"):
            qualname = f"{cls.__class__.__qualname__}.{frame_info.function}"
    except Exception:  # noqa: BLE001
        pass
    return {
        "file": frame_info.filename,
        "line": frame_info.lineno,
        "function": frame_info.function,
        "qualname": qualname,
    }


def stack_tail(exc: BaseException, *, limit: int = 3) -> list[str]:
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__, limit=limit)
    return [line.rstrip("\n") for line in lines if line.strip()]


def _from_tb(finfo: traceback.FrameSummary) -> dict[str, Any]:
    return {
        "file": finfo.filename,
        "line": finfo.lineno,
        "function": finfo.name,
        "qualname": finfo.name,
    }
