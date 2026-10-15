"""Tin tức mặc định + bài viết thành viên (tab Tin tức / Bài viết)."""

from __future__ import annotations

import streamlit as st

from datasource.news import fetch_news
from datasource.posts import add_post, list_posts
from engine.identity import current_username


def show_news_section() -> None:
    st.subheader("Tin tức")
    st.caption("Nguồn mặc định: RSS CafeF · Thị trường chứng khoán. Cache 30 phút trong data/news_cache.json.")
    if st.button("Làm mới tin", key="news_refresh"):
        from config import NEWS_CACHE_PATH

        try:
            NEWS_CACHE_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        st.rerun()
    try:
        items = fetch_news()
    except Exception as error:
        st.warning(f"Không tải được tin: {error}")
        return
    if not items:
        st.info("Chưa có tin.")
        return
    for item in items:
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
    st.caption(f"Đăng với tên «{username}». Lưu tại data/member_posts.json.")

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
    for post in posts:
        st.markdown(f"### {post['title']}")
        st.caption(f"{post['author']} · {post['created_at'][:19]}")
        st.write(post["body"])
        st.divider()


def show_news_and_posts() -> None:
    show_news_section()
    st.divider()
    show_member_posts()
