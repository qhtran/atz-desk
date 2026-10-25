"""Async-safe WebSocket connection manager for priceboard fan-out."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from backend.observability import ERR_PB_WS, log, setup

setup("ws")
COMPONENT = "ws"


class ConnectionManager:
    """Track live clients and broadcast JSON/text safely under concurrency."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        log(COMPONENT, "WS-CONNECT", "client connected", clients=len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        log(COMPONENT, "WS-DISCONNECT", "client disconnected", clients=len(self._connections))

    async def send_personal(self, websocket: WebSocket, message: str) -> None:
        try:
            await websocket.send_text(message)
        except Exception:
            await self.disconnect(websocket)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            targets = list(self._connections)
        if not targets:
            return

        stale: list[WebSocket] = []

        async def _send(ws: WebSocket) -> None:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        await asyncio.gather(*(_send(ws) for ws in targets), return_exceptions=True)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._connections.discard(ws)
            log(
                COMPONENT,
                "WS-STALE",
                "removed stale websocket clients",
                logging.WARNING,
                error_code=ERR_PB_WS,
                removed=len(stale),
                remaining=len(self._connections),
            )

    async def broadcast_json(self, payload: dict) -> None:
        import json

        await self.broadcast(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
