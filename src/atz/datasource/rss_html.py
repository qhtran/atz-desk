"""Sanitize / làm sạch HTML mô tả RSS (CafeF…). Không chạy script."""

from __future__ import annotations

import re
from html import escape, unescape
from html.parser import HTMLParser

_ALLOWED = {"a", "br", "p", "b", "i", "strong", "em", "ul", "ol", "li", "img"}
_VOID = {"br", "img"}


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name not in _ALLOWED:
            if name not in _VOID:
                self._skip += 1
            return
        if self._skip:
            return
        if name == "a":
            href = ""
            for key, value in attrs:
                if key.lower() == "href" and value and value.startswith(("http://", "https://")):
                    href = value
                    break
            if href:
                self.out.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">')
            return
        if name == "img":
            src = alt = ""
            for key, value in attrs:
                low = key.lower()
                if low == "src" and value and value.startswith(("http://", "https://")):
                    src = value
                if low == "alt" and value:
                    alt = value
            if src:
                self.out.append(
                    f'<img src="{escape(src, quote=True)}" alt="{escape(alt)}" '
                    f'style="max-width:100%;height:auto;border-radius:4px;margin:4px 0"/>'
                )
            return
        if name in _VOID:
            self.out.append(f"<{name}>")
            return
        self.out.append(f"<{name}>")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name not in _ALLOWED:
            if name not in _VOID and self._skip:
                self._skip -= 1
            return
        if self._skip:
            return
        if name not in _VOID:
            self.out.append(f"</{name}>")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.out.append(escape(data))


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in {"script", "style"}:
            self._skip += 1
            return
        if name == "br" and not self._skip:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip:
            self._skip -= 1


def sanitize_rss_html(raw: str) -> str:
    """Giữ thẻ an toàn (a/img/br/p/…) để render UI."""
    text = unescape(str(raw or "")).strip()
    if not text:
        return ""
    if "<" not in text:
        return escape(text)
    parser = _Sanitizer()
    try:
        # Không bọc thẻ ngoài: thẻ không nằm trong allowlist sẽ bị bỏ (và bỏ luôn nội dung con).
        parser.feed(text)
        parser.close()
    except Exception:
        return escape(re.sub(r"<[^>]+>", " ", text))
    html = "".join(parser.out).strip()
    return html or escape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip())


def html_to_text(raw: str) -> str:
    """Plain text cho caption / test."""
    text = unescape(str(raw or "")).strip()
    if not text:
        return ""
    if "<" not in text:
        return text
    parser = _TextOnly()
    try:
        parser.feed(f"<div>{text}</div>")
        parser.close()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()
