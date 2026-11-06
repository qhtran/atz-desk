"""Scoring Matrix evaluate engine — decision support (no order placement).

Labels: STRONG_BUY | ACCUMULATE | HOLD | TRIM | SELL
"""

from __future__ import annotations

from typing import Any

DECISIONS = ("STRONG_BUY", "ACCUMULATE", "HOLD", "TRIM", "SELL")

# Vietnamese short labels for UI (decision support — not order placement).
DECISION_LABELS_VI: dict[str, str] = {
    "STRONG_BUY": "Mua mạnh",
    "ACCUMULATE": "Tích lũy",
    "HOLD": "Giữ",
    "TRIM": "Giảm",
    "SELL": "Bán",
}

# score_pct thresholds (inclusive lower bound)
_DECISION_BANDS: list[tuple[float, str]] = [
    (80.0, "STRONG_BUY"),
    (60.0, "ACCUMULATE"),
    (40.0, "HOLD"),
    (20.0, "TRIM"),
    (0.0, "SELL"),
]

_OPS = {
    "eq": lambda a, b: a == b,
    "==": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "!=": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    ">": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    ">=": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "<": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "<=": lambda a, b: a <= b,
}


def decision_from_score_pct(score_pct: float) -> str:
    pct = float(score_pct)
    for lo, label in _DECISION_BANDS:
        if pct >= lo:
            return label
    return "SELL"


def decision_label_vi(decision: str) -> str:
    key = str(decision or "").strip().upper()
    return DECISION_LABELS_VI.get(key, key or "—")


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _eval_clause(clause: dict[str, Any], indicators: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate one condition clause against indicator map."""
    if not isinstance(clause, dict):
        return False, "invalid clause"
    # Nested boolean groups
    if "all" in clause:
        kids = clause.get("all") or []
        if not isinstance(kids, list) or not kids:
            return False, "empty all"
        notes = []
        for kid in kids:
            ok, note = _eval_clause(kid, indicators)
            notes.append(note)
            if not ok:
                return False, "all: " + "; ".join(notes)
        return True, "all ok"
    if "any" in clause:
        kids = clause.get("any") or []
        if not isinstance(kids, list) or not kids:
            return False, "empty any"
        notes = []
        for kid in kids:
            ok, note = _eval_clause(kid, indicators)
            notes.append(note)
            if ok:
                return True, "any: " + note
        return False, "any failed: " + "; ".join(notes)

    field = str(clause.get("field") or "").strip()
    op = str(clause.get("op") or "gte").strip().lower()
    if not field:
        return False, "field required"
    raw = indicators.get(field)
    left = _num(raw)
    if left is None and op not in {"eq", "==", "ne", "!="}:
        return False, f"{field} missing"

    if op in {"between", "in_range"}:
        bounds = clause.get("value")
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            return False, "between needs [lo, hi]"
        lo, hi = _num(bounds[0]), _num(bounds[1])
        if left is None or lo is None or hi is None:
            return False, f"{field} between invalid"
        ok = lo <= left <= hi
        return ok, f"{field}={left} between [{lo},{hi}] → {ok}"

    right = clause.get("value")
    if op in {"eq", "==", "ne", "!="} and not isinstance(right, (int, float)):
        # string compare
        ok = _OPS[op](str(raw), str(right))
        return ok, f"{field}={raw!r} {op} {right!r} → {ok}"

    right_n = _num(right)
    if left is None or right_n is None:
        return False, f"{field} cmp invalid"
    fn = _OPS.get(op)
    if fn is None:
        return False, f"unknown op {op}"
    ok = bool(fn(left, right_n))
    return ok, f"{field}={left} {op} {right_n} → {ok}"


def evaluate_rules(
    rules: list[dict[str, Any]],
    indicators: dict[str, Any],
) -> dict[str, Any]:
    """Run active rules; return total/max/pct/decision/breakdown."""
    breakdown: list[dict[str, Any]] = []
    total = 0.0
    max_score = 0.0

    for rule in rules:
        if rule.get("is_active") is False:
            continue
        weight = float(rule.get("weight") or 0)
        # Max score = sum of positive weights (negative weights are penalties when hit)
        if weight > 0:
            max_score += weight
        cond = rule.get("condition_json") or {}
        hit, detail = _eval_clause(cond if isinstance(cond, dict) else {}, indicators)
        earned = weight if hit else 0.0
        if hit:
            total += weight
        breakdown.append(
            {
                "rule_code": rule.get("rule_code"),
                "category": rule.get("category"),
                "name": rule.get("name"),
                "weight": weight,
                "hit": hit,
                "earned": round(earned, 4),
                "detail": detail,
            }
        )

    if max_score <= 0:
        # All-negative or empty matrix → map raw total into HOLD-ish band via clamp
        score_pct = 50.0 if not breakdown else max(0.0, min(100.0, 50.0 + total))
    else:
        score_pct = max(0.0, min(100.0, (total / max_score) * 100.0))

    decision = decision_from_score_pct(score_pct)
    return {
        "total_score": round(total, 4),
        "max_score": round(max_score, 4),
        "score_pct": round(score_pct, 4),
        "decision": decision,
        "decision_label": decision_label_vi(decision),
        "breakdown": breakdown,
    }


# Seed rules for empty DB (quant decision-support defaults)
DEFAULT_SEED_RULES: list[dict[str, Any]] = [
    {
        "rule_code": "RSI_OK",
        "category": "momentum",
        "name": "RSI trong vùng tích lũy (40–65)",
        "weight": 20,
        "condition_json": {"field": "rsi", "op": "between", "value": [40, 65]},
        "is_active": True,
    },
    {
        "rule_code": "TREND_MA",
        "category": "trend",
        "name": "Giá trên MA20",
        "weight": 25,
        "condition_json": {"field": "price_vs_ma20", "op": "gt", "value": 0},
        "is_active": True,
    },
    {
        "rule_code": "MACD_POS",
        "category": "momentum",
        "name": "MACD histogram > 0",
        "weight": 20,
        "condition_json": {"field": "macd_hist", "op": "gt", "value": 0},
        "is_active": True,
    },
    {
        "rule_code": "VOL_EXP",
        "category": "volume",
        "name": "Khối lượng ≥ 1.2× TB",
        "weight": 15,
        "condition_json": {"field": "vol_ratio", "op": "gte", "value": 1.2},
        "is_active": True,
    },
    {
        "rule_code": "PCT_SOFT",
        "category": "price",
        "name": "Biến động phiên không quá nóng (< 4%)",
        "weight": 20,
        "condition_json": {"field": "change_pct", "op": "lt", "value": 4},
        "is_active": True,
    },
]
