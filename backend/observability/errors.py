"""Domain exceptions with stable error codes."""

from __future__ import annotations

from backend.observability.origin import capture_origin


class PriceboardError(Exception):
    """Raised for priceboard business/infra faults; carries ERR-PB-* and origin."""

    def __init__(self, error_code: str, message: str, *, cause: BaseException | None = None) -> None:
        self.error_code = error_code
        self.origin = capture_origin(exc=cause) if cause else capture_origin(depth=2)
        self.cause = cause
        super().__init__(message)
