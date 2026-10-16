"""Kiểu dữ liệu, config, log, rate limiter, mã lỗi dùng chung cho index feed."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ingestion.log import log as _log
from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "index.yaml"

ERR_IDX_PROVIDER_OPEN = "ERR-IDX-001"   # circuit một provider OPEN
ERR_IDX_ALL_DOWN = "ERR-IDX-002"        # không provider nào trả được một mã
ERR_IDX_PARSE = "ERR-IDX-003"           # response sai định dạng
ERR_IDX_REDIS = "ERR-IDX-004"           # ghi Redis lỗi
ERR_IDX_FUTURES = "ERR-IDX-005"         # không xác định được hợp đồng phái sinh hiện hành

NAMES = {"VNINDEX": "Chỉ số VNINDEX", "HNXINDEX": "Chỉ số HNXINDEX", "UPCOMINDEX": "Chỉ số UPCOMINDEX",
         "VN30": "Chỉ số VN30", "VN30F1M": "Hợp đồng tương lai VN30F1M", "VN30F2M": "Hợp đồng tương lai VN30F2M"}
FUTURES = ("VN30F1M", "VN30F2M")


def log(action: str, message: str, level: int = 20, **kw) -> None:
    _log("IDX-" + action, message, level, **kw)


class ProviderDown(Exception):
    pass


@dataclass
class IdxQuote:
    symbol: str
    value: float
    ref: float
    source: str
    data_time: str | None = None   # giờ của bản tin phía nguồn (ISO) nếu có
    contract: str | None = None    # mã hợp đồng phái sinh (41I1...)

    @property
    def change(self) -> float:
        return round(self.value - self.ref, 2)

    @property
    def pct(self) -> float:
        return round((self.value - self.ref) / self.ref * 100, 2) if self.ref else 0.0


@dataclass
class Settings:
    symbols: list[str]
    providers: list[str]
    poll_trading: float
    poll_off: float
    sessions: list[list[str]]
    timezone: str
    spark_max: int
    futures_resolve_seconds: float
    lookback_days: int
    user_agent: str
    provider_settings: dict
    redis_url: str
    quote_key: str
    spark_key: str
    health_key: str
    quote_ttl: int
    health_max_age: float
    env: dict = field(default_factory=dict)


def load(path=None) -> Settings:
    path = Path(path or os.environ.get("IDX_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    i, r = doc["index"], doc["redis"]
    return Settings(
        symbols=[s.upper() for s in i["symbols"]], providers=[p.upper() for p in i["providers"]],
        poll_trading=float(i["poll_seconds_trading"]), poll_off=float(i["poll_seconds_off"]),
        sessions=i["trading_sessions"], timezone=i["timezone"], spark_max=int(i["spark_max_points"]),
        futures_resolve_seconds=float(i["futures_resolve_seconds"]), lookback_days=int(i["backfill_lookback_days"]),
        user_agent=i["user_agent"], provider_settings=i["provider_settings"],
        redis_url=os.environ.get("REDIS_URL") or r["url"], quote_key=r["quote_key"], spark_key=r["spark_key"],
        health_key=r["health_key"], quote_ttl=int(r["quote_ttl_seconds"]), health_max_age=float(r["health_max_age_seconds"]),
        env={k: os.environ.get(k, "") for k in ("SSI_CONSUMER_ID", "SSI_CONSUMER_SECRET")},
    )


class Bucket:
    """Token bucket không chặn: try_acquire(n) -> False thì bỏ qua provider ở chu kỳ này."""

    def __init__(self, rpm: float, clock=time.monotonic, burst: float | None = None):
        self.rate = rpm / 60.0
        self.cap = max(1.0, burst if burst is not None else rpm / 6.0)   # mặc định ~10s burst
        self.tokens = self.cap
        self.clock = clock
        self.t = clock()
        self.lock = threading.Lock()
        self.granted = 0
        self.denied = 0

    def try_acquire(self, n: int = 1) -> bool:
        with self.lock:
            now = self.clock()
            self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)
            self.t = now
            if self.tokens >= n:
                self.tokens -= n
                self.granted += n
                return True
            self.denied += n
            return False
