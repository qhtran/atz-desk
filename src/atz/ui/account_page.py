"""Trang Tài khoản theme VANTIQ (Phase 1: chỉ đọc header Authentik, không gọi API)."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import urlparse

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "account.yaml"
_URL_KEYS = ("logout_url", "password_flow_url", "mfa_flow_url")


def safe_url(value: object) -> str:
    """Chỉ nhận URL https có host. Còn lại trả '' để không render link lạ (javascript:, http://...)."""
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    return text


def load_account_config(path: Path | str | None = None) -> dict:
    """Đọc block `account` trong config/account.yaml. Thiếu file thì tắt trang."""
    path = Path(path or DEFAULT_PATH)
    if not path.exists():
        return {"enabled": False, **{key: "" for key in _URL_KEYS}}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = doc.get("account") or {}
    config = {"enabled": bool(block.get("enabled", True))}
    for key in _URL_KEYS:
        config[key] = safe_url(block.get(key))
    return config


def profile_card_html(me: dict) -> str:
    """Thẻ hồ sơ. Mọi giá trị từ header được escape trước khi chèn HTML."""
    from ui.brand import BRAND_NAME
    from ui.theme_tokens import BG_CARD, REF, TEXT_MUTED, TEXT_PRIMARY

    name = html.escape(me.get("name") or me["username"])
    username = html.escape(me["username"])
    email = html.escape(me.get("email") or "—")
    chips = "".join(
        f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 10px;'
        f'border:1px solid {REF};border-radius:12px;color:{REF};font-size:0.85rem">'
        f"{html.escape(group)}</span>"
        for group in me.get("groups") or []
    ) or f'<span style="color:{TEXT_MUTED}">Chưa thuộc nhóm nào</span>'
    return (
        f'<div style="background:{BG_CARD};border-radius:10px;padding:18px 20px;margin-bottom:12px">'
        f'<div style="color:{TEXT_MUTED};font-size:0.8rem;letter-spacing:0.08em">{BRAND_NAME} · TÀI KHOẢN</div>'
        f'<div style="color:{TEXT_PRIMARY};font-size:1.4rem;font-weight:700;margin:4px 0">{name}</div>'
        f'<div style="color:{TEXT_MUTED}">@{username} · {email}</div>'
        f'<div style="margin-top:10px">{chips}</div>'
        "</div>"
    )


def logout_link_html(url: str) -> str:
    """Link đăng xuất mở cùng tab, để outpost xóa cookie rồi bắt đăng nhập lại."""
    from ui.theme_tokens import DOWN, TEXT_PRIMARY

    href = html.escape(safe_url(url), quote=True)
    if not href:
        return ""
    return (
        f'<a href="{href}" target="_self" style="display:inline-block;padding:8px 18px;'
        f'border-radius:8px;background:{DOWN};color:{TEXT_PRIMARY};font-weight:600;'
        f'text-decoration:none">Đăng xuất</a>'
    )


def show_account(config: dict | None = None) -> None:
    import streamlit as st

    from engine.identity import current_me

    config = config or load_account_config()
    st.subheader("Tài khoản")
    me = current_me()
    if me is None:
        st.warning("Chưa đăng nhập: không có header Authentik (chạy local hoặc ngoài nginx).")
        return
    st.markdown(profile_card_html(me), unsafe_allow_html=True)
    st.markdown("**Bảo mật**")
    columns = st.columns(2)
    if config["password_flow_url"]:
        columns[0].link_button("Đổi mật khẩu", config["password_flow_url"], width="stretch")
    if config["mfa_flow_url"]:
        columns[1].link_button("Cài xác thực 2 lớp (TOTP)", config["mfa_flow_url"], width="stretch")
    st.caption("Đổi mật khẩu và 2FA mở trang auth.atz.vn trong tab mới.")
    logout = logout_link_html(config["logout_url"])
    if logout:
        # Điều hướng cả trang làm phiên Streamlit cũ kết thúc, session_state bị bỏ theo.
        st.markdown(logout, unsafe_allow_html=True)
    else:
        st.caption("Chưa cấu hình account.logout_url trong config/account.yaml.")
