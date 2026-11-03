"""WebSocket /ws/stream/alerts — real-time quant alert contract (Option B)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from backend.identity import resolve_me
from backend.observability import ERR_PB_WS, log, setup
from backend.websocket_manager import ConnectionManager

setup("ws_alerts")
COMPONENT = "ws_alerts"


def _desk_cookie(websocket: WebSocket) -> str | None:
    try:
        from backend.desk_session import COOKIE_NAME

        return websocket.cookies.get(COOKIE_NAME)
    except Exception:
        return None


def resolve_ws_identity(websocket: WebSocket) -> dict[str, Any] | None:
    """ForwardAuth headers or desk session cookie (DEV)."""
    try:
        return resolve_me(websocket.headers, desk_cookie=_desk_cookie(websocket))
    except Exception:
        return None


def alerts_ws_require_auth() -> bool:
    """Hard gate when ``ALERTS_WS_REQUIRE_AUTH=1`` (optional; default off)."""
    return (os.getenv("ALERTS_WS_REQUIRE_AUTH") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def run_alerts_ws(
    websocket: WebSocket,
    alert_manager: ConnectionManager,
    *,
    channel: str = "stream_alerts",
    require_auth: bool | None = None,
) -> None:
    """Shared handler for ``/ws/stream/alerts`` and ``/ws/alerts`` alias."""
    must_auth = alerts_ws_require_auth() if require_auth is None else bool(require_auth)
    me = resolve_ws_identity(websocket)
    if must_auth and not me:
        await websocket.accept()
        await websocket.send_text('{"type":"error","detail":"auth required"}')
        await websocket.close(code=4401)
        return

    await alert_manager.connect(websocket)
    try:
        hello = {
            "type": "hello",
            "channel": channel,
            "authenticated": bool(me),
            "username": (me or {}).get("username") or None,
        }
        await alert_manager.send_personal(websocket, json.dumps(hello, ensure_ascii=False))
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() in {"ping", '{"type":"ping"}'}:
                await alert_manager.send_personal(websocket, '{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log(
            COMPONENT,
            "WS-ALERTS",
            "websocket handler error",
            logging.WARNING,
            error_code=ERR_PB_WS,
            exc=exc,
        )
    finally:
        await alert_manager.disconnect(websocket)


def register_alerts_ws(app, alert_manager: ConnectionManager) -> None:
    """Attach legacy Option B path (SPA Alerts tab)."""

    @app.websocket("/ws/stream/alerts")
    async def ws_stream_alerts(websocket: WebSocket) -> None:
        await run_alerts_ws(
            websocket,
            alert_manager,
            channel="stream_alerts",
            require_auth=False,
        )
