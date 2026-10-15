"""Hợp đồng chung của một filter. UI và engine chỉ đọc các kiểu này."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str
    default: Any
    label: str
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class FilterSpec:
    name: str
    label: str
    description: str
    group: str
    params: tuple[ParamSpec, ...]


@dataclass(frozen=True)
class SignalResult:
    matched: bool
    signal_type: str
    strength: float | None
    reason: str
    details: dict[str, Any]


def waiting(reason: str = "không đủ dữ liệu") -> SignalResult:
    return SignalResult(False, "cho", None, reason, {})


def hit(signal_type: str, reason: str, details: dict[str, Any], strength: float = 1.0) -> SignalResult:
    return SignalResult(True, signal_type, strength, reason, details)


def hold(reason: str, details: dict[str, Any] | None = None) -> SignalResult:
    return SignalResult(False, "giu", None, reason, details or {})


def resolve_params(spec: FilterSpec, params: dict[str, Any] | None) -> dict[str, Any]:
    """Điền default rồi ép kiểu theo metadata. Giá trị lạ của choice quay về default."""
    raw = dict(params or {})
    resolved: dict[str, Any] = {}
    for item in spec.params:
        value = raw.get(item.name, item.default)
        if item.kind == "int":
            value = int(value)
        elif item.kind == "float":
            value = float(value)
        elif item.kind == "bool":
            value = bool(value)
        elif item.kind == "choice":
            value = str(value)
            if item.choices and value not in item.choices:
                value = item.default
        if item.kind in {"int", "float"} and item.min is not None and value < item.min:
            value = int(item.min) if item.kind == "int" else float(item.min)
        if item.kind in {"int", "float"} and item.max is not None and value > item.max:
            value = int(item.max) if item.kind == "int" else float(item.max)
        resolved[item.name] = value
    return resolved
