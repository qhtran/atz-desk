"""Tin tức mặc định + bài viết thành viên (tab Tin tức / Bài viết)."""

from __future__ import annotations

import math

import streamlit as st

from datasource.news import fetch_news
from datasource.posts import (
    add_post,
    can_modify_post,
    delete_post,
    list_posts,
    update_post,
)
from engine.identity import current_username

NEWS_PAGE_SIZE = 10


def show_news_section() -> None:
    st.subheader("Tin tức")
    st.caption(
        "Nguồn mặc định: RSS CafeF · Thị trường chứng khoán. "
        f"Cache 30 phút trong data/news_cache.json. {NEWS_PAGE_SIZE} tin mỗi trang."
    )
    if st.button("Làm mới tin", key="news_refresh"):
        from config import NEWS_CACHE_PATH

        try:
            NEWS_CACHE_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        st.session_state.pop("news_page", None)
        st.rerun()
    try:
        items = fetch_news()
    except Exception as error:
        st.warning(f"Không tải được tin: {error}")
        return
    if not items:
        st.info("Chưa có tin.")
        return

    total = len(items)
    pages = max(1, math.ceil(total / NEWS_PAGE_SIZE))
    current = int(st.session_state.get("news_page", 1) or 1)
    if current < 1 or current > pages:
        st.session_state["news_page"] = 1
    # Một key dùng chung cho nút và selectbox, tránh lệch trang.

    def _shift(delta: int) -> None:
        value = int(st.session_state.get("news_page", 1)) + delta
        st.session_state["news_page"] = min(max(value, 1), pages)

    pager = st.container(key="news_pager")
    controls = pager.columns([1, 2, 1, 2])
    controls[0].button(
        "← Trước",
        key="news_prev",
        disabled=int(st.session_state.get("news_page", 1)) <= 1,
        width="stretch",
        on_click=_shift,
        args=(-1,),
    )
    controls[1].selectbox(
        "Trang",
        options=list(range(1, pages + 1)),
        key="news_page",
        label_visibility="collapsed",
    )
    controls[2].button(
        "Sau →",
        key="news_next",
        disabled=int(st.session_state.get("news_page", 1)) >= pages,
        width="stretch",
        on_click=_shift,
        args=(1,),
    )
    page = int(st.session_state.get("news_page", 1))
    controls[3].caption(f"Trang {page}/{pages} · {total} tin")

    start = (page - 1) * NEWS_PAGE_SIZE
    chunk = items[start : start + NEWS_PAGE_SIZE]
    for item in chunk:
        title = item.get("title") or "(không tiêu đề)"
        link = item.get("link") or ""
        if link:
            st.markdown(f"**[{title}]({link})**")
        else:
            st.markdown(f"**{title}**")
        summary = (item.get("summary") or "").strip()
        if summary:
            st.caption(summary)
        meta = " · ".join(
            part
            for part in (
                str(item.get("source") or ""),
                str(item.get("published") or "")[:19],
            )
            if part
        )
        if meta:
            st.caption(meta)


def show_member_posts() -> None:
    st.subheader("Bài viết của thành viên")
    username = current_username()
    st.caption(
        f"Đăng với tên «{username}». Chỉ tác giả mới sửa/xóa bài của mình. "
        "Lưu tại data/member_posts.json."
    )

    with st.form("member_post_form"):
        title = st.text_input("Tiêu đề", key="post_title")
        body = st.text_area("Nội dung", key="post_body", height=120)
        submitted = st.form_submit_button("Đăng bài")
    if submitted:
        try:
            add_post(username, title, body)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Đã đăng bài.")
            st.rerun()

    posts = list_posts()
    if not posts:
        st.info("Chưa có bài viết.")
        return

    editing_id = st.session_state.get("editing_post_id")
    for post in posts:
        st.markdown(f"### {post['title']}")
        st.caption(f"{post['author']} · {post['created_at'][:19]}")
        own = can_modify_post(post, username)
        if editing_id == post["id"] and own:
            with st.form(f"edit_post_{post['id']}"):
                new_title = st.text_input("Sửa tiêu đề", value=post["title"], key=f"edit_title_{post['id']}")
                new_body = st.text_area(
                    "Sửa nội dung",
                    value=post["body"],
                    height=120,
                    key=f"edit_body_{post['id']}",
                )
                save = st.form_submit_button("Lưu chỉnh sửa")
            if st.button("Hủy chỉnh sửa", key=f"cancel_edit_{post['id']}"):
                st.session_state.pop("editing_post_id", None)
                st.rerun()
            if save:
                try:
                    update_post(username, post["id"], new_title, new_body)
                except (ValueError, PermissionError, LookupError) as error:
                    st.error(str(error))
                else:
                    st.session_state.pop("editing_post_id", None)
                    st.success("Đã cập nhật bài viết.")
                    st.rerun()
        else:
            st.write(post["body"])
            if own:
                actions = st.columns(2)
                if actions[0].button("Sửa", key=f"edit_btn_{post['id']}"):
                    st.session_state["editing_post_id"] = post["id"]
                    st.rerun()
                if actions[1].button("Xóa", key=f"del_btn_{post['id']}"):
                    try:
                        delete_post(username, post["id"])
                    except (PermissionError, LookupError) as error:
                        st.error(str(error))
                    else:
                        if st.session_state.get("editing_post_id") == post["id"]:
                            st.session_state.pop("editing_post_id", None)
                        st.success("Đã xóa bài viết.")
                        st.rerun()
        st.divider()


def show_news_and_posts() -> None:
    show_news_section()
    st.divider()
    show_member_posts()
