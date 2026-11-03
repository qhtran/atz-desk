"""WebSocket ``/ws/alerts`` — Milestone 4 alias of Option B stream alerts.

Delegates to ``backend.ws_alerts.run_alerts_ws`` (same Redis-fan-out manager).
Optional hard auth: set env ``ALERTS_WS_REQUIRE_AUTH=1``. Soft identity is
always resolved into the hello payload when cookie/headers are present.
"""

from __future__ import annotations

from fastapi import WebSocket

from backend.websocket_manager import ConnectionManager
from backend.ws_alerts import alerts_ws_require_auth, run_alerts_ws


def register_alerts_ws_alias(app, alert_manager: ConnectionManager) -> None:
    """Register ``/ws/alerts`` next to legacy ``/ws/stream/alerts``."""

    @app.websocket("/ws/alerts")
    async def ws_alerts(websocket: WebSocket) -> None:
        # Alias path: respect optional env gate; soft identity always in hello.
        await run_alerts_ws(
            websocket,
            alert_manager,
            channel="alerts",
            require_auth=alerts_ws_require_auth(),
        )
