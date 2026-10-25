"""Trace middleware — X-Request-ID."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_healthz_has_request_id() -> None:
    res = client.get("/healthz", headers={"X-Request-ID": "test-trace-abc"})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == "test-trace-abc"


def test_healthz_generates_request_id() -> None:
    res = client.get("/healthz")
    assert res.status_code == 200
    tid = res.headers.get("X-Request-ID")
    assert tid and len(tid) >= 8
