"""Bài viết thành viên lưu JSON trong data/member_posts.json."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import config


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_author(author: str | None) -> str:
    """Chuẩn hoá tên tác giả. Rỗng hoặc thiếu thì 'local'."""
    name = (author or "").strip()
    return name or "local"


def can_modify_post(post: dict, username: str | None) -> bool:
    """Chỉ đúng tác giả (sau normalize) mới được sửa/xóa."""
    return normalize_author(post.get("author")) == normalize_author(username)


def _read_all() -> list[dict]:
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
                "author": normalize_author(item.get("author")),
                "created_at": str(item.get("created_at") or _now()),
                "updated_at": str(item.get("updated_at") or item.get("created_at") or _now()),
            }
        )
    cleaned.sort(key=lambda row: row["created_at"], reverse=True)
    return cleaned


def _write_all(posts: list[dict]) -> None:
    config.POSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.POSTS_PATH.write_text(
        json.dumps({"posts": posts, "updated_at": _now()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_posts(limit: int = 50) -> list[dict]:
    return _read_all()[:limit]


def get_post(post_id: str) -> dict | None:
    target = str(post_id)
    for item in _read_all():
        if item["id"] == target:
            return item
    return None


def add_post(author: str, title: str, body: str) -> dict:
    heading = title.strip()
    content = body.strip()
    if not heading:
        raise ValueError("Cần tiêu đề.")
    if not content:
        raise ValueError("Cần nội dung.")
    posts = _read_all()
    now = _now()
    item = {
        "id": str(uuid.uuid4()),
        "title": heading,
        "body": content,
        "author": normalize_author(author),
        "created_at": now,
        "updated_at": now,
    }
    posts.insert(0, item)
    _write_all(posts)
    return item


def update_post(username: str, post_id: str, title: str, body: str) -> dict:
    """Sửa bài. Chỉ tác giả mới được. Không tìm thấy hoặc không đủ quyền thì lỗi."""
    heading = title.strip()
    content = body.strip()
    if not heading:
        raise ValueError("Cần tiêu đề.")
    if not content:
        raise ValueError("Cần nội dung.")
    posts = _read_all()
    target = str(post_id)
    for index, item in enumerate(posts):
        if item["id"] != target:
            continue
        if not can_modify_post(item, username):
            raise PermissionError("Chỉ tác giả mới được sửa bài này.")
        item["title"] = heading
        item["body"] = content
        item["updated_at"] = _now()
        posts[index] = item
        _write_all(posts)
        return item
    raise LookupError("Không tìm thấy bài viết.")


def delete_post(username: str, post_id: str) -> None:
    """Xóa bài. Chỉ tác giả mới được."""
    posts = _read_all()
    target = str(post_id)
    kept: list[dict] = []
    found = None
    for item in posts:
        if item["id"] == target:
            found = item
            continue
        kept.append(item)
    if found is None:
        raise LookupError("Không tìm thấy bài viết.")
    if not can_modify_post(found, username):
        raise PermissionError("Chỉ tác giả mới được xóa bài này.")
    _write_all(kept)
