"""Bài viết thành viên lưu JSON trong data/member_posts.json."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import config


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_posts(limit: int = 50) -> list[dict]:
    if not config.POSTS_PATH.exists():
        return []
    try:
        payload = json.loads(config.POSTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        if not title and not body:
            continue
        cleaned.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "title": title or "(không tiêu đề)",
                "body": body,
                "author": str(item.get("author") or "local"),
                "created_at": str(item.get("created_at") or _now()),
            }
        )
    cleaned.sort(key=lambda row: row["created_at"], reverse=True)
    return cleaned[:limit]


def add_post(author: str, title: str, body: str) -> dict:
    heading = title.strip()
    content = body.strip()
    if not heading:
        raise ValueError("Cần tiêu đề.")
    if not content:
        raise ValueError("Cần nội dung.")
    posts = list_posts(limit=500)
    item = {
        "id": str(uuid.uuid4()),
        "title": heading,
        "body": content,
        "author": (author or "local").strip() or "local",
        "created_at": _now(),
    }
    posts.insert(0, item)
    config.POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.POSTS_PATH.write_text(
        json.dumps({"posts": posts, "updated_at": _now()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return item
