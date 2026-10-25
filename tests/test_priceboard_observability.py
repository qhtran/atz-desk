"""Structured log + error codes for dev.atz.vn priceboard."""

from __future__ import annotations

import json
import logging
import re

import pytest

from backend.observability import ERR_PB_REDIS, REGISTRY, PriceboardError, log, setup
from backend.observability.codes import ERR_PB_SCREENER

LABEL = re.compile(
    r"^\[DBG-\d{8}-\d{4}-PB-([A-Z0-9-]+)\](?: (ERR-PB-\d{3}))? (\{.*\})$"
)


@pytest.fixture(autouse=True)
def _cap(caplog):
    caplog.set_level(logging.DEBUG, logger="atz.priceboard.api")
    setup("api", level="DEBUG")


def _parse_lines(caplog):
    out = []
    for rec in caplog.records:
        if rec.name != "atz.priceboard.api":
            continue
        line = rec.getMessage()
        m = LABEL.match(line)
        assert m, f"log thiếu debug label đúng format: {line}"
        data = json.loads(m.group(3))
        for key in ("debug_label", "error_code", "module", "message"):
            assert key in data, (key, line)
        assert data["module"] == "PB"
        assert data["error_code"] == m.group(2)
        out.append((m.group(1), data, line))
    return out


def test_registry_covers_all_codes():
    assert len(REGISTRY) == 9
    assert ERR_PB_REDIS in REGISTRY
    assert ERR_PB_SCREENER in REGISTRY


def test_log_error_includes_origin(caplog):
    try:
        raise ValueError("boom")
    except ValueError as exc:
        log("api", "TEST", "failure", logging.ERROR, error_code=ERR_PB_REDIS, exc=exc)
    _action, data, _line = _parse_lines(caplog)[0]
    assert data["error_code"] == ERR_PB_REDIS
    assert "origin" in data
    assert data["origin"]["file"]
    assert data["origin"]["line"] > 0
    assert data["origin"]["function"]
    assert data["exc_type"] == "ValueError"
    assert "boom" in data["exc_message"]


def test_priceboard_error_carries_code():
    err = PriceboardError(ERR_PB_SCREENER, "bad rule")
    assert err.error_code == ERR_PB_SCREENER
    assert err.origin["line"] > 0


def test_screener_invalid_rules():
    from backend.screener import find_invalid_raw_rules

    assert find_invalid_raw_rules([{"field": "volume", "op": "nope", "value": 1}])
    assert not find_invalid_raw_rules([{"field": "volume", "op": "gte", "value": 1}])
