"""Username lấy từ header Authentik, không thì local."""

from __future__ import annotations

from engine.identity import username_from_headers


def test_header_wins() -> None:
    assert username_from_headers({"X-Authentik-Username": " hoa "}) == "hoa"


def test_missing_header_is_local() -> None:
    assert username_from_headers({}) == "local"
    assert username_from_headers(None) == "local"
    assert username_from_headers({"X-Authentik-Username": "  "}) == "local"
