"""Composite rule screener for priceboard rows (no Streamlit).

FilterEngine applies an ordered list of field/op/value rules with safe
numeric coercion (None / NaN / bad strings never raise).

Rule dict shape:
  {"field": "volume"|"change_pct"|"change"|"last"|"ref"|"kind"|"symbol"|...,
   "op": "gte"|"gt"|"lte"|"lt"|"eq"|"neq"|"in"|"contains",
   "value": <scalar|list>}

Composite:
  mode "and" (default) — every rule must pass
  mode "or" — any rule passes (empty rules → pass all equities)
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from backend.board_universe import INDEX_SYMBOL_SET

ALLOWED_OPS = frozenset({"gte", "gt", "lte", "lt", "eq", "neq", "in", "contains"})
INDEX_KINDS = frozenset({"index"})
INDEX_SYMBOLS = INDEX_SYMBOL_SET

# Built-in client-friendly presets (FE can merge with custom params).
PRESETS: dict[str, dict[str, Any]] = {
    "up2": {
        "label": "Tăng ≥ 2%",
        "mode": "and",
        "rules": [{"field": "change_pct", "op": "gte", "value": 2}],
    },
    "down2": {
        "label": "Giảm ≤ -2%",
        "mode": "and",
        "rules": [{"field": "change_pct", "op": "lte", "value": -2}],
    },
    "volhi": {
        "label": "KL ≥ 1M",
        "mode": "and",
        "rules": [{"field": "volume", "op": "gte", "value": 1_000_000}],
    },
}


def safe_float(value: Any, default: float | None = None) -> float | None:
    """Coerce to finite float; None / NaN / Inf / junk → default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if not s or s.lower() in {"nan", "none", "null", "-", "—"}:
            return default
        try:
            f = float(s)
        except ValueError:
            return default
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        s = str(value).strip()
    except Exception:  # noqa: BLE001
        return default
    if s.lower() in {"nan", "none", "null"}:
        return default
    return s


def is_index_row(row: Mapping[str, Any]) -> bool:
    kind = safe_str(row.get("kind")).lower()
    if kind in INDEX_KINDS:
        return True
    return safe_str(row.get("symbol")).upper() in INDEX_SYMBOLS


def normalize_rule(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        return None
    field = safe_str(raw.get("field")).lower()
    op = safe_str(raw.get("op")).lower()
    if not field or op not in ALLOWED_OPS:
        return None
    return {"field": field, "op": op, "value": raw.get("value")}


def find_invalid_raw_rules(raw_rules: Any) -> list[str]:
    """Return human-readable errors for API validation (ERR-PB-008)."""
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        return ["rules: expected a list"]
    out: list[str] = []
    for i, item in enumerate(raw_rules):
        if not isinstance(item, Mapping):
            out.append(f"rules[{i}]: expected object")
            continue
        field = safe_str(item.get("field")).lower()
        op = safe_str(item.get("op")).lower()
        if not field:
            out.append(f"rules[{i}]: missing field")
        if not op or op not in ALLOWED_OPS:
            out.append(f"rules[{i}]: unsupported op {op!r}")
    return out


def normalize_rules(raw_rules: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        return []
    out: list[dict[str, Any]] = []
    for item in raw_rules:
        rule = normalize_rule(item)
        if rule is not None:
            out.append(rule)
    return out


def _field_value(row: Mapping[str, Any], field: str) -> Any:
    # Aliases used by FE / tick contract
    aliases = {
        "pct": "change_pct",
        "changepercent": "change_pct",
        "vol": "volume",
        "price": "last",
        "matched": "last",
    }
    key = aliases.get(field, field)
    if key in row:
        return row.get(key)
    # case-insensitive fallback
    lower_map = {str(k).lower(): v for k, v in row.items()}
    return lower_map.get(key)


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "contains":
        return safe_str(right).upper() in safe_str(left).upper()

    if op == "in":
        if isinstance(right, (list, tuple, set, frozenset)):
            hay = {safe_str(x).upper() for x in right}
            return safe_str(left).upper() in hay
        return safe_str(left).upper() == safe_str(right).upper()

    # Numeric ops prefer float; fall back to string eq/neq
    lf = safe_float(left)
    rf = safe_float(right)
    if lf is not None and rf is not None:
        if op == "gte":
            return lf >= rf
        if op == "gt":
            return lf > rf
        if op == "lte":
            return lf <= rf
        if op == "lt":
            return lf < rf
        if op == "eq":
            return lf == rf
        if op == "neq":
            return lf != rf

    ls = safe_str(left).upper()
    rs = safe_str(right).upper()
    if op == "eq":
        return ls == rs
    if op == "neq":
        return ls != rs
    # Non-numeric inequality → fail closed
    return False


def eval_rule(row: Mapping[str, Any], rule: Mapping[str, Any]) -> bool:
    field = safe_str(rule.get("field")).lower()
    op = safe_str(rule.get("op")).lower()
    if not field or op not in ALLOWED_OPS:
        return False
    left = _field_value(row, field)
    # Missing numeric field → fail closed for comparisons (except neq on missing)
    if left is None and op in {"gte", "gt", "lte", "lt", "eq"}:
        return False
    return _compare(op, left, rule.get("value"))


class FilterEngine:
    """AND/OR composite filter over tick-like dict rows."""

    def __init__(
        self,
        rules: Sequence[Mapping[str, Any]] | None = None,
        *,
        mode: str = "and",
        include_index: bool = False,
    ) -> None:
        self.rules = normalize_rules(list(rules or []))
        m = safe_str(mode, "and").lower()
        self.mode = m if m in {"and", "or"} else "and"
        self.include_index = bool(include_index)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> FilterEngine:
        data = payload or {}
        return cls(
            rules=data.get("rules") or [],
            mode=str(data.get("mode") or "and"),
            include_index=bool(data.get("include_index") or False),
        )

    def match(self, row: Mapping[str, Any] | None) -> bool:
        if not isinstance(row, Mapping):
            return False
        if not self.include_index and is_index_row(row):
            return False
        if not self.rules:
            return True
        # Work on a shallow copy so near-limit markers never mutate Redis cache
        work: MutableMapping[str, Any] = dict(row)
        annotate_near_limits(work)
        if self.mode == "or":
            return any(eval_rule(work, r) for r in self.rules)
        return all(eval_rule(work, r) for r in self.rules)

    def filter_rows(self, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            if self.match(row):
                out.append(dict(row))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "include_index": self.include_index,
            "rules": self.rules,
        }


def build_compose_rules(
    *,
    volume_min: Any = None,
    change_pct_min: Any = None,
    change_pct_max: Any = None,
    flags: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Helper used by API/FE docs: compose volume / % / named flags.

    flags: up2, down2, volhi, ceil, floor (ceil/floor need last≈ceil/floor — handled as
    special fields via optional rules on FE; here we map up2/down2/volhi only plus
    numeric params).
    Returns (rules, mode). mode is "and" when combining params; named exclusive
    presets stay "and" with a single rule group.
    """
    rules: list[dict[str, Any]] = []
    vol = safe_float(volume_min)
    if vol is not None and vol > 0:
        rules.append({"field": "volume", "op": "gte", "value": vol})

    pmin = safe_float(change_pct_min)
    if pmin is not None:
        rules.append({"field": "change_pct", "op": "gte", "value": pmin})

    pmax = safe_float(change_pct_max)
    if pmax is not None:
        rules.append({"field": "change_pct", "op": "lte", "value": pmax})

    for flag in flags or []:
        f = safe_str(flag).lower()
        if f == "up2":
            rules.append({"field": "change_pct", "op": "gte", "value": 2})
        elif f == "down2":
            rules.append({"field": "change_pct", "op": "lte", "value": -2})
        elif f == "volhi":
            rules.append({"field": "volume", "op": "gte", "value": 1_000_000})
        elif f == "ceil":
            # Relative: last >= ref * 1.065 approx poorly; use field sentinel
            # Real ceil match: last == ceil (eq) — only if both present
            rules.append({"field": "_near_ceil", "op": "eq", "value": 1})
        elif f == "floor":
            rules.append({"field": "_near_floor", "op": "eq", "value": 1})

    return rules, "and"


def annotate_near_limits(row: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Add _near_ceil / _near_floor markers for compose flags (safe)."""
    last = safe_float(row.get("last"))
    ceil = safe_float(row.get("ceil"))
    floor = safe_float(row.get("floor"))
    row["_near_ceil"] = 1 if (last is not None and ceil is not None and last == ceil) else 0
    row["_near_floor"] = 1 if (last is not None and floor is not None and last == floor) else 0
    return row
