"""Đọc config yaml + ghi đè env. Không hardcode trong code khác."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "ingestion.yaml"


@dataclass(frozen=True)
class Settings:
    primary_source: str
    fallback_source: str
    poll_interval_seconds: float
    batch_size: int
    safety_max_rpm: int
    request_timeout_seconds: float
    failure_threshold: int
    recovery_timeout_seconds: float
    breaker_window_seconds: float
    retries: int
    retry_backoff_seconds: float
    retry_jitter_seconds: float
    limiter_burst: int
    throttle_warn_ratio: float
    degraded_interval_multiplier: float
    degraded_max_interval_seconds: float
    off_hours_poll_interval_seconds: float
    trading_hours: str
    timezone: str
    redis_url: str
    quote_key: str
    quote_ttl_seconds: int
    stream: str
    stream_maxlen: int
    health_key: str
    health_max_age_seconds: float
    symbols: list[str] = field(default_factory=list)


def _env(name: str, value, cast):
    raw = os.environ.get(name)
    return cast(raw) if raw not in (None, "") else value


def load(path: str | os.PathLike | None = None) -> Settings:
    path = Path(path or os.environ.get("INGEST_CONFIG") or DEFAULT_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    ing, red = doc["ingestion"], doc["redis"]
    cb = ing["circuit_breaker"]
    symbols = _env("INGEST_SYMBOLS", doc.get("symbols", []), lambda s: s.split(","))
    return Settings(
        primary_source=_env("INGEST_PRIMARY_SOURCE", ing["primary_source"], str).upper(),
        fallback_source=_env("INGEST_FALLBACK_SOURCE", ing["fallback_source"], str).upper(),
        poll_interval_seconds=_env("INGEST_POLL_INTERVAL_SECONDS", ing["poll_interval_seconds"], float),
        batch_size=_env("INGEST_BATCH_SIZE", ing["batch_size"], int),
        safety_max_rpm=_env("INGEST_SAFETY_MAX_RPM", ing["safety_max_rpm"], int),
        request_timeout_seconds=_env("INGEST_REQUEST_TIMEOUT_SECONDS", ing["request_timeout_seconds"], float),
        failure_threshold=_env("INGEST_CB_FAILURE_THRESHOLD", cb["failure_threshold"], int),
        recovery_timeout_seconds=_env("INGEST_CB_RECOVERY_TIMEOUT_SECONDS", cb["recovery_timeout_seconds"], float),
        breaker_window_seconds=float(ing.get("circuit_breaker_window_seconds", 60)),
        retries=_env("INGEST_RETRIES", ing.get("retries", 2), int),
        retry_backoff_seconds=float(ing.get("retry_backoff_seconds", 0.5)),
        retry_jitter_seconds=float(ing.get("retry_jitter_seconds", 0.5)),
        limiter_burst=int(ing.get("limiter_burst", 10)),
        throttle_warn_ratio=float(ing.get("throttle_warn_ratio", 0.2)),
        degraded_interval_multiplier=float(ing.get("degraded_interval_multiplier", 4)),
        degraded_max_interval_seconds=float(ing.get("degraded_max_interval_seconds", 60)),
        off_hours_poll_interval_seconds=_env("INGEST_OFF_HOURS_POLL_SECONDS", ing.get("off_hours_poll_interval_seconds", 60), float),
        trading_hours=str(ing.get("trading_hours", "09:00-15:00")),
        timezone=str(ing.get("timezone", "Asia/Ho_Chi_Minh")),
        redis_url=_env("REDIS_URL", red["url"], str),
        quote_key=red["quote_key"],
        quote_ttl_seconds=_env("INGEST_QUOTE_TTL_SECONDS", red["quote_ttl_seconds"], int),
        stream=red["stream"],
        stream_maxlen=int(red["stream_maxlen"]),
        health_key=red["health_key"],
        health_max_age_seconds=float(red["health_max_age_seconds"]),
        symbols=[s.strip().upper() for s in symbols if s.strip()],
    )
