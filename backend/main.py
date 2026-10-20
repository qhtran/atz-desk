"""FastAPI entry: static frontend + WebSocket /ws/priceboard."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.redis_listener import HASH_KEY, REDIS_URL, RedisTickListener, load_snapshot
from backend.websocket_manager import ConnectionManager

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger("atz.priceboard.api")

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend"))

manager = ConnectionManager()
listener = RedisTickListener(manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    listener.start()
    logger.info("DBG-PRICEBOARD-API-START frontend=%s redis=%s", FRONTEND_DIR, REDIS_URL)
    yield
    await listener.stop()
    logger.info("DBG-PRICEBOARD-API-STOP")


app = FastAPI(title="atz priceboard", version="0.1.0-dev", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    ok = False
    try:
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        ok = (await r.ping()) is True
        await r.aclose()
    except Exception as exc:
        logger.warning("DBG-PRICEBOARD-HEALTH-REDIS-ERR err=%s", exc)
    return {
        "ok": ok,
        "clients": manager.client_count,
        "hash": HASH_KEY,
    }


@app.websocket("/ws/priceboard")
async def ws_priceboard(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        rows = await load_snapshot(redis)
        await manager.send_personal(
            websocket,
            json.dumps(
                {"type": "snapshot", "rows": rows, "source": "redis_hash"},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        # Keepalive: client may send ping; we also tolerate idle until nginx timeout.
        while True:
            msg = await websocket.receive_text()
            if msg in ("ping", '{"type":"ping"}'):
                await manager.send_personal(websocket, '{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("DBG-PRICEBOARD-WS-ERR err=%s", exc)
    finally:
        await redis.aclose()
        await manager.disconnect(websocket)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
