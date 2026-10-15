"""Tin tức mặc định: RSS công khai, cache JSON; lỗi thì trả placeholder có cấu trúc."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

import config

# CafeF tin mới — RSS công khai, không cần API key.
_RSS_URL = "https://cafef.vn/thi-truong-chung-khoan.rss"
_CACHE_MAX_AGE_SECONDS = 1800
_USER_AGENT = "vnstocks/1.0 (+https://atz.vn)"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _placeholder() -> list[dict]:
    return [
        {
            "title": "Chưa tải được tin tức realtime",
            "summary": (
                "Khung tin tức sẵn sàng. Nguồn mặc định là RSS CafeF thị trường chứng khoán. "
                "Khi mạng hoặc nguồn lỗi, khu vực này giữ cấu trúc title / summary / link / published."
            ),
            "link": "https://cafef.vn/thi-truong-chung-khoan.chn",
            "published": _now(),
            "source": "placeholder",
        }
    ]


def _parse_rss(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    items = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        link = (node.findtext("link") or "").strip()
        summary = (node.findtext("description") or "").strip()
        # strip simple HTML tags from description
        if "<" in summary:
            try:
                summary = "".join(ET.fromstring(f"<div>{summary}</div>").itertext())
            except ET.ParseError:
                summary = summary.replace("<br>", " ").replace("<br/>", " ")
        published_raw = (node.findtext("pubDate") or "").strip()
        published = published_raw
        if published_raw:
            try:
                published = parsedate_to_datetime(published_raw).astimezone(timezone.utc).isoformat()
            except Exception:
                published = published_raw
        items.append(
            {
                "title": title,
                "summary": summary[:400],
                "link": link,
                "published": published,
                "source": "cafef.rss",
            }
        )
    return items


def _read_cache() -> list[dict] | None:
    if not config.NEWS_CACHE_PATH.exists():
        return None
    try:
        payload = json.loads(config.NEWS_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    fetched = payload.get("fetched_at")
    items = payload.get("items")
    if not fetched or not isinstance(items, list):
        return None
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched.replace("Z", "+00:00"))
    except ValueError:
        return None
    if age.total_seconds() > _CACHE_MAX_AGE_SECONDS:
        return None
    return items


def _write_cache(items: list[dict]) -> None:
    config.NEWS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.NEWS_CACHE_PATH.write_text(
        json.dumps({"fetched_at": _now(), "items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_news(limit: int = 12) -> list[dict]:
    cached = _read_cache()
    if cached is not None:
        return cached[:limit]
    try:
        request = Request(_RSS_URL, headers={"User-Agent": _USER_AGENT})
        with urlopen(request, timeout=12) as response:
            raw = response.read()
        items = _parse_rss(raw)
        if not items:
            items = _placeholder()
        else:
            _write_cache(items)
        return items[:limit]
    except Exception:
        return _placeholder()[:limit]
