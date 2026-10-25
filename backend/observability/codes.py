"""Priceboard error codes (dev.atz.vn). Registry is source of truth for docs/tests."""

from __future__ import annotations

from dataclasses import dataclass

ERR_PB_REDIS = "ERR-PB-001"
ERR_PB_REDIS_IO = "ERR-PB-002"
ERR_PB_CONFIG = "ERR-PB-003"
ERR_PB_SSI_AUTH = "ERR-PB-004"
ERR_PB_SSI_SESSION = "ERR-PB-005"
ERR_PB_PARSE = "ERR-PB-006"
ERR_PB_WS = "ERR-PB-007"
ERR_PB_SCREENER = "ERR-PB-008"
ERR_PB_SSI_FALLBACK = "ERR-PB-009"


@dataclass(frozen=True, slots=True)
class ErrorCode:
    id: str
    summary: str


REGISTRY: dict[str, ErrorCode] = {
    ERR_PB_REDIS: ErrorCode(ERR_PB_REDIS, "Redis unreachable / ping fail"),
    ERR_PB_REDIS_IO: ErrorCode(ERR_PB_REDIS_IO, "Redis pub/sub or hash write failed"),
    ERR_PB_CONFIG: ErrorCode(ERR_PB_CONFIG, "Priceboard YAML config load failed"),
    ERR_PB_SSI_AUTH: ErrorCode(ERR_PB_SSI_AUTH, "SSI auth / access token failed"),
    ERR_PB_SSI_SESSION: ErrorCode(ERR_PB_SSI_SESSION, "SSI WebSocket session error or reconnect"),
    ERR_PB_PARSE: ErrorCode(ERR_PB_PARSE, "SSI tick / envelope parse failed"),
    ERR_PB_WS: ErrorCode(ERR_PB_WS, "WebSocket client stale or handler error"),
    ERR_PB_SCREENER: ErrorCode(ERR_PB_SCREENER, "Screener request or rule invalid"),
    ERR_PB_SSI_FALLBACK: ErrorCode(ERR_PB_SSI_FALLBACK, "SSI requested but credentials missing — mock fallback"),
}
