"""Trading-station API errors (ERR-TS-*)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

ERR_TS_VALIDATION = "ERR-TS-001"
ERR_TS_NOT_FOUND = "ERR-TS-002"
ERR_TS_BUSINESS = "ERR-TS-003"
ERR_TS_INTERNAL = "ERR-TS-004"


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = ERR_TS_BUSINESS,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


def trace_id_from_request(request: Request) -> str:
    tid = getattr(request.state, "trace_id", None)
    return str(tid or "unknown")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    tid = trace_id_from_request(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "trace_id": tid,
            "message": exc.message,
        },
        headers={"X-Request-ID": tid},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    tid = trace_id_from_request(request)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": ERR_TS_INTERNAL,
            "trace_id": tid,
            "message": "Internal server error",
        },
        headers={"X-Request-ID": tid},
    )
