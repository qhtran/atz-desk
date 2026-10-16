"""Danh mục theo dõi: mặc định theo ngành + danh mục riêng của user (JSON trong data/)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config
from config import UNIVERSE
from engine.runner import load_symbol_csv

_TOP_PER_SECTOR = 8
_VOLUME_BARS = 10


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _user_path(username: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in username.strip()) or "local"
    return config.WATCHLISTS_DIR / f"{safe}.json"


def load_user_watchlists(username: str) -> list[dict]:
    """Đọc danh mục riêng. File lỗi hoặc thiếu thì trả list rỗng, không ném lỗi."""
    path = _user_path(username)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("lists") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        symbols = [
            str(symbol).strip().upper()
            for symbol in (item.get("symbols") or [])
            if str(symbol).strip()
        ]
        result.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "name": name,
                "symbols": symbols,
                "created_at": str(item.get("created_at") or _now()),
            }
        )
    return result


def save_user_watchlists(username: str, lists: list[dict]) -> None:
    config.WATCHLISTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _user_path(username)
    payload = {"username": username, "lists": lists, "updated_at": _now()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_watchlist(username: str, name: str, symbols: list[str] | None = None) -> dict:
    title = name.strip()
    if not title:
        raise ValueError("Cần đặt tên danh mục.")
    lists = load_user_watchlists(username)
    if any(item["name"].lower() == title.lower() for item in lists):
        raise ValueError(f"Đã có danh mục tên «{title}».")
    item = {
        "id": str(uuid.uuid4()),
        "name": title,
        "symbols": [s.strip().upper() for s in (symbols or []) if s.strip()],
        "created_at": _now(),
    }
    lists.append(item)
    save_user_watchlists(username, lists)
    return item


def delete_watchlist(username: str, list_id: str) -> None:
    lists = [item for item in load_user_watchlists(username) if item["id"] != list_id]
    save_user_watchlists(username, lists)


def set_watchlist_symbols(username: str, list_id: str, symbols: list[str]) -> dict | None:
    lists = load_user_watchlists(username)
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    # unique keep order
    seen: set[str] = set()
    unique: list[str] = []
    for symbol in cleaned:
        if symbol not in seen:
            seen.add(symbol)
            unique.append(symbol)
    for item in lists:
        if item["id"] == list_id:
            item["symbols"] = unique
            save_user_watchlists(username, lists)
            return item
    return None


def add_symbol(username: str, list_id: str, symbol: str) -> dict | None:
    code = symbol.strip().upper()
    if not code:
        raise ValueError("Thiếu mã.")
    lists = load_user_watchlists(username)
    for item in lists:
        if item["id"] == list_id:
            if code not in item["symbols"]:
                item["symbols"].append(code)
                save_user_watchlists(username, lists)
            return item
    return None


def remove_symbol(username: str, list_id: str, symbol: str) -> dict | None:
    code = symbol.strip().upper()
    lists = load_user_watchlists(username)
    for item in lists:
        if item["id"] == list_id:
            item["symbols"] = [s for s in item["symbols"] if s != code]
            save_user_watchlists(username, lists)
            return item
    return None


def _avg_volume_10(symbol: str) -> float | None:
    try:
        frame = load_symbol_csv(config.BARS_DIR, symbol)
    except Exception:
        return None
    if frame is None or frame.empty or "volume" not in frame.columns:
        return None
    volume = pd.to_numeric(frame["volume"], errors="coerce").dropna().tail(_VOLUME_BARS)
    if len(volume) < _VOLUME_BARS:
        return None
    average = float(volume.mean())
    return average if average > 0 else None


def load_industry_map() -> dict[str, str]:
    """Mã → ngành. Thiếu file hoặc lỗi đọc thì {}."""
    if not config.INDUSTRY_PATH.exists():
        return {}
    try:
        table = pd.read_csv(config.INDUSTRY_PATH)
    except Exception:
        return {}
    if "symbol" not in table.columns or "icb_name" not in table.columns:
        return {}
    symbols = table["symbol"].astype(str).str.upper()
    names = table["icb_name"].astype(str)
    return {symbol: name for symbol, name in zip(symbols, names) if symbol and name and name != "nan"}


def default_sector_watchlists(universe: list[str] | None = None) -> list[dict]:
    """Danh mục mặc định theo ngành, ưu tiên KL TB 10 phiên cao.

    Không có dữ liệu ngành thì trả list rỗng (caller hiện thông báo).
    """
    industries = load_industry_map()
    if not industries:
        return []
    symbols = [item.strip().upper() for item in (universe if universe is not None else UNIVERSE)]
    grouped: dict[str, list[tuple[str, float]]] = {}
    for symbol in symbols:
        industry = industries.get(symbol)
        if not industry:
            continue
        volume = _avg_volume_10(symbol)
        rank = volume if volume is not None else -1.0
        grouped.setdefault(industry, []).append((symbol, rank))
    result = []
    for industry in sorted(grouped):
        ranked = sorted(grouped[industry], key=lambda item: item[1], reverse=True)
        codes = [symbol for symbol, _ in ranked[:_TOP_PER_SECTOR]]
        volumes = {symbol: vol for symbol, vol in ranked if vol > 0}
        result.append(
            {
                "id": f"sector:{industry}",
                "name": industry,
                "symbols": codes,
                "kind": "sector",
                "volumes": volumes,
            }
        )
    return result
