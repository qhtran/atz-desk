"""WebSocket /ws/stream/alerts — real-time quant alert contract (Option B)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.observability import ERR_PB_WS, log, setup
from backend.websocket_manager import ConnectionManager

setup("ws_alerts")
COMPONENT = "ws_alerts"

router = APIRouter()


def register_alerts_ws(app, alert_manager: ConnectionManager) -> None:
    """Attach WS route to FastAPI app (avoids circular import with lifespan)."""

    @app.websocket("/ws/stream/alerts")
    async def ws_stream_alerts(websocket: WebSocket) -> None:
        await alert_manager.connect(websocket)
        try:
            await alert_manager.send_personal(
                websocket,
                '{"type":"hello","channel":"stream_alerts"}',
            )
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
