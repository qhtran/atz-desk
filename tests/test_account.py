"""Trang Tài khoản Phase 1: parse header Authentik, config và HTML an toàn. Không gọi mạng."""

from __future__ import annotations

from pathlib import Path

from engine.identity import me_from_headers
from ui.account_page import load_account_config, logout_link_html, profile_card_html, safe_url

HEADERS = {
    "X-Authentik-Username": " hoa ",
    "X-Authentik-Email": "hoa@example.com",
    "X-Authentik-Name": "Trần Hoa",
    "X-Authentik-Uid": "abc123",
    "X-Authentik-Groups": "members| vip |",
}


def test_me_from_full_headers() -> None:
    me = me_from_headers(HEADERS)
    assert me == {
        "username": "hoa",
        "email": "hoa@example.com",
        "name": "Trần Hoa",
        "uid": "abc123",
        "groups": ["members", "vip"],
    }


def test_header_names_are_case_insensitive() -> None:
    me = me_from_headers({"x-authentik-username": "an", "X-AUTHENTIK-GROUPS": "a"})
    assert me is not None and me["username"] == "an" and me["groups"] == ["a"]
    assert me["email"] == "" and me["name"] == ""


def test_missing_username_is_not_logged_in() -> None:
    assert me_from_headers(None) is None
    assert me_from_headers({}) is None
    assert me_from_headers({"X-Authentik-Username": "  ", "X-Authentik-Email": "a@b.c"}) is None
    assert me_from_headers({"X-Authentik-Email": "a@b.c"}) is None


def test_safe_url_only_https() -> None:
    assert safe_url("https://auth.atz.vn/if/flow/x/") == "https://auth.atz.vn/if/flow/x/"
    assert safe_url("javascript:alert(1)") == ""
    assert safe_url("http://atz.vn/") == ""
    assert safe_url("") == "" and safe_url(None) == ""


def test_config_loads_and_filters_urls(tmp_path: Path) -> None:
    path = tmp_path / "account.yaml"
    path.write_text(
        "account:\n  enabled: true\n  logout_url: 'https://atz.vn/outpost.goauthentik.io/sign_out'\n"
        "  password_flow_url: 'javascript:x'\n  mfa_flow_url: ''\n",
        encoding="utf-8",
    )
    config = load_account_config(path)
    assert config == {
        "enabled": True,
        "logout_url": "https://atz.vn/outpost.goauthentik.io/sign_out",
        "password_flow_url": "",
        "mfa_flow_url": "",
    }


def test_missing_config_disables_page(tmp_path: Path) -> None:
    assert load_account_config(tmp_path / "none.yaml")["enabled"] is False


def test_repo_config_is_valid() -> None:
    config = load_account_config()
    assert config["enabled"] is True
    assert config["logout_url"].startswith("https://")


def test_profile_card_escapes_header_values() -> None:
    me = me_from_headers({**HEADERS, "X-Authentik-Name": "<script>x</script>", "X-Authentik-Groups": "<b>g</b>"})
    card = profile_card_html(me)
    assert "<script>" not in card and "&lt;script&gt;" in card
    assert "<b>g</b>" not in card and "&lt;b&gt;g&lt;/b&gt;" in card
    assert "@hoa" in card and "VANTIQ" in card


def test_logout_link_same_tab_and_rejects_bad_url() -> None:
    link = logout_link_html("https://atz.vn/outpost.goauthentik.io/sign_out")
    assert 'target="_self"' in link and 'href="https://atz.vn/outpost.goauthentik.io/sign_out"' in link
    assert logout_link_html("javascript:alert(1)") == ""
