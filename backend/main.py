"""FastAPI entry: static frontend + WebSocket /ws/priceboard + screener API."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.core.database import init_db
from backend.core.errors import AppError, app_error_handler
from backend.core.logging_middleware import TraceMiddleware
from backend.modules.trading.router import router as trading_router
from backend.redis_listener import HASH_KEY, REDIS_URL, RedisTickListener, load_snapshot
from backend.screener import PRESETS, FilterEngine, build_compose_rules
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
    init_db()
    listener.start()
    logger.info("DBG-PRICEBOARD-API-START frontend=%s redis=%s", FRONTEND_DIR, REDIS_URL)
    yield
    await listener.stop()
    logger.info("DBG-PRICEBOARD-API-STOP")


app = FastAPI(title="atz priceboard", version="0.1.0-dev", lifespan=lifespan)
app.add_middleware(TraceMiddleware)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(trading_router)


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


class ScreenerRule(BaseModel):
    field: str
    op: str
    value: Any = None


class ScreenerRequest(BaseModel):
    """Screen Redis snapshot (or optional inline rows) with composite rules."""

    mode: str = "and"
    include_index: bool = False
    rules: list[ScreenerRule] = Field(default_factory=list)
    # Convenience compose (merged as AND with rules)
    volume_min: float | None = None
    change_pct_min: float | None = None
    change_pct_max: float | None = None
    flags: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] | None = None


@app.get("/api/screener/presets")
async def screener_presets() -> dict:
    return {"presets": PRESETS, "ops": sorted(["gte", "gt", "lte", "lt", "eq", "neq", "in", "contains"])}


@app.post("/api/screener")
async def screener_run(body: ScreenerRequest) -> dict:
    compose_rules, _ = build_compose_rules(
        volume_min=body.volume_min,
        change_pct_min=body.change_pct_min,
        change_pct_max=body.change_pct_max,
        flags=body.flags,
    )
    merged = [r.model_dump() for r in body.rules] + compose_rules
    engine = FilterEngine(merged, mode=body.mode, include_index=body.include_index)

    if body.rows is not None:
        source_rows = body.rows
        source = "inline"
    else:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            source_rows = await load_snapshot(redis)
            source = "redis_hash"
        finally:
            await redis.aclose()

    matched = engine.filter_rows(source_rows)
    logger.info(
        "DBG-PRICEBOARD-SCREENER matched=%s total=%s mode=%s rules=%s source=%s",
        len(matched),
        len(source_rows),
        engine.mode,
        len(engine.rules),
        source,
    )
    return {
        "ok": True,
        "source": source,
        "engine": engine.to_dict(),
        "total": len(source_rows),
        "matched": len(matched),
        "rows": matched,
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


@app.get("/trading")
async def trading_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "trading.html")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
