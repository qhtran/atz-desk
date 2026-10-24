"""Observability for dev.atz.vn priceboard stack."""

from backend.observability.codes import (
    ERR_PB_CONFIG,
    ERR_PB_PARSE,
    ERR_PB_REDIS,
    ERR_PB_REDIS_IO,
    ERR_PB_SCREENER,
    ERR_PB_SSI_AUTH,
    ERR_PB_SSI_FALLBACK,
    ERR_PB_SSI_SESSION,
    ERR_PB_WS,
    REGISTRY,
)
from backend.observability.errors import PriceboardError
from backend.observability.logging import get_logger, label, log, setup

__all__ = [
    "ERR_PB_CONFIG",
    "ERR_PB_PARSE",
    "ERR_PB_REDIS",
    "ERR_PB_REDIS_IO",
    "ERR_PB_SCREENER",
    "ERR_PB_SSI_AUTH",
    "ERR_PB_SSI_FALLBACK",
    "ERR_PB_SSI_SESSION",
    "ERR_PB_WS",
    "REGISTRY",
    "PriceboardError",
    "get_logger",
    "label",
    "log",
    "setup",
]
