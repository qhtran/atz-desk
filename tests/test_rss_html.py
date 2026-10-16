"""Sanitize HTML mô tả RSS."""

from __future__ import annotations

from datasource.rss_html import html_to_text, sanitize_rss_html


def test_html_to_text_strips_tags():
    raw = '<p>Giá <b>VIC</b> tăng<br/>mạnh <script>x()</script></p>'
    text = html_to_text(raw)
    assert "VIC" in text and "script" not in text.lower()
    assert "<" not in text


def test_sanitize_keeps_safe_link_and_drops_script():
    raw = '<p>Xem <a href="https://cafef.vn/a">tin</a></p><script>alert(1)</script>'
    html = sanitize_rss_html(raw)
    assert 'href="https://cafef.vn/a"' in html
    assert "<script" not in html
    assert "alert" not in html
