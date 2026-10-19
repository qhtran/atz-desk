"""Load config/ssi_stream.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "ssi_stream.yaml"


@dataclass
class StreamSettings:
    enabled: bool
    url: str
    mode: str
    auth_url: str
    silence_trading: float
    silence_off: float
    reconnect_initial: float
    reconnect_max: float
    sessions: list[list[str]]
    timezone: str
    topics: list[str]
    aliases: dict[str, str]
    spark_max: int
    redis_url: str
    quote_key: str
    spark_key: str
    health_key: str
    quote_ttl: int
    consumer_id: str = ""
    consumer_secret: str = ""


def load(path=None) -> StreamSettings:
    path = Path(path or os.environ.get("SSI_STREAM_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    s, r = doc["ssi_stream"], doc["redis"]
    return StreamSettings(
        enabled=bool(s.get("enabled", True)),
        url=str(s["url"]),
        mode=str(s.get("mode", "websocket_primary")),
        auth_url=str(s.get("auth_url", "https://api.ssi.com.vn/api/v3/auth/token")),
        silence_trading=float(s.get("silence_seconds_trading", 20)),
        silence_off=float(s.get("silence_seconds_off", 180)),
        reconnect_initial=float(s.get("reconnect_initial_seconds", 2)),
        reconnect_max=float(s.get("reconnect_max_seconds", 60)),
        sessions=list(s.get("trading_sessions") or [["08:45", "11:30"], ["13:00", "15:00"]]),
        timezone=str(s.get("timezone", "Asia/Ho_Chi_Minh")),
        topics=list(s.get("topics") or []),
        aliases={str(k): str(v).upper() for k, v in (s.get("symbol_aliases") or {}).items()},
        spark_max=int(s.get("spark_max_points", 300)),
        redis_url=os.environ.get("REDIS_URL") or r["url"],
        quote_key=r["quote_key"],
        spark_key=r["spark_key"],
        health_key=r["health_key"],
        quote_ttl=int(r["quote_ttl_seconds"]),
        consumer_id=os.environ.get("SSI_CONSUMER_ID", ""),
        consumer_secret=os.environ.get("SSI_CONSUMER_SECRET", ""),
    )
