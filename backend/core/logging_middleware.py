"""X-Request-ID propagation + structured JSON access logs."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("atz.trace")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get("x-request-id", "").strip()
        trace_id = incoming or str(uuid.uuid4())
        request.state.trace_id = trace_id
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            status = response.status_code if response is not None else 500
            if response is not None:
                response.headers["X-Request-ID"] = trace_id
            payload = {
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": elapsed_ms,
            }
            logger.info(json.dumps(payload, ensure_ascii=False))
