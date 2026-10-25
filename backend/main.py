"""FastAPI entry: static frontend + WebSocket /ws/priceboard + screener API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.debug_ui import public_debug_ui_config
from backend.portfolio_alerts import position_alert
from backend.identity import me_from_headers
from backend.portfolio_f3 import batch_f3_alerts, load_f3_sector_themes
from backend.portfolio_quotes import normalize_symbols, resolve_portfolio_quotes
from backend.portfolio_store import list_positions, migrate_if_empty, replace_positions
from backend.observability import ERR_PB_REDIS, ERR_PB_SCREENER, ERR_PB_WS, log, setup
from backend.redis_listener import HASH_KEY, REDIS_URL, RedisTickListener, load_snapshot
from backend.screener import PRESETS, FilterEngine, build_compose_rules, find_invalid_raw_rules
from backend.websocket_manager import ConnectionManager

setup("api")
COMPONENT = "api"

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend"))

manager = ConnectionManager()
listener = RedisTickListener(manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    listener.start()
    log(COMPONENT, "API-START", "priceboard api started", frontend=str(FRONTEND_DIR), redis_url=REDIS_URL)
    yield
    await listener.stop()
    log(COMPONENT, "API-STOP", "priceboard api stopped")


app = FastAPI(title="atz priceboard", version="0.1.0-dev", lifespan=lifespan)


@app.get("/api/debug-ui/config")
async def debug_ui_config() -> JSONResponse:
    """Bootstrap gate for priceboard Inspect overlay (no secrets)."""
    return JSONResponse(public_debug_ui_config())


@app.get("/healthz")
async def healthz() -> dict:
    ok = False
    try:
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        ok = (await r.ping()) is True
        await r.aclose()
    except Exception as exc:
        log(
            COMPONENT,
            "HEALTH-REDIS",
            "redis ping failed",
            logging.WARNING,
            error_code=ERR_PB_REDIS,
            exc=exc,
        )
    return {
        "ok": ok,
        "clients": manager.client_count,
        "hash": HASH_KEY,
    }


class ScreenerRule(BaseModel):
    field: str
    op: str
    value: Any = None


class PortfolioAlertItem(BaseModel):
    symbol: str
    avg: float | None = None
    last: float | None = None
    support: float | None = None
    resistance: float | None = None


class PortfolioAlertsRequest(BaseModel):
    items: list[PortfolioAlertItem] = Field(default_factory=list)


@app.post("/api/portfolio/intraday-alerts")
async def portfolio_intraday_alerts(body: PortfolioAlertsRequest) -> dict:
    """Cảnh báo intraday (±% / hỗ trợ-kháng cự) — Phase A spec PORTFOLIO_DEV_FROM_PROD."""
    alerts: dict[str, str] = {}
    for item in body.items:
        sym = str(item.symbol or "").strip().upper()
        if not sym:
            continue
        alerts[sym] = position_alert(
            item.avg,
            item.last,
            support=item.support,
            resistance=item.resistance,
        )
    return {"ok": True, "alerts": alerts}


@app.get("/api/portfolio/quotes")
async def portfolio_quotes(symbols: str = "") -> dict:
    """Giá + KL TB 10 phiên — priceboard hash → OHLCV → legacy quote:* (Phase B)."""
    syms = normalize_symbols(symbols)
    if not syms:
        return {"ok": True, "quotes": {}, "priceboard_hits": 0, "priced": 0}
    quotes, pb_hits, priced = await asyncio.to_thread(resolve_portfolio_quotes, syms)
    return {"ok": True, "quotes": quotes, "priceboard_hits": pb_hits, "priced": priced}


class PortfolioF3AlertsRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)


@app.get("/api/portfolio/sectors/f3")
async def portfolio_sectors_f3() -> dict:
    """Danh sách ngành F3 (read-only sector_themes_f3.yaml)."""
    themes = await asyncio.to_thread(load_f3_sector_themes)
    return {"ok": True, "themes": themes}


@app.post("/api/portfolio/alerts")
async def portfolio_f3_alerts(body: PortfolioF3AlertsRequest) -> dict:
    """Cảnh báo F3 khung ngày — Phase C (không re-run mỗi tick WS)."""
    syms = normalize_symbols(body.symbols)
    if not syms:
        return {"ok": True, "alerts": {}}
    alerts = await asyncio.to_thread(batch_f3_alerts, syms)
    return {"ok": True, "alerts": alerts}


class PortfolioPositionItem(BaseModel):
    symbol: str
    qty: float
    avg: float = 0
    support: float | None = None
    resistance: float | None = None


class PortfolioPositionsBody(BaseModel):
    items: list[PortfolioPositionItem] = Field(default_factory=list)


def _require_authentik_user(request: Request) -> str:
    me = me_from_headers(request.headers)
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


@app.get("/api/account/me")
async def account_me(request: Request) -> dict:
    """Identity từ header ForwardAuth (dev/prod nginx)."""
    me = me_from_headers(request.headers)
    if not me:
        return {"ok": True, "authenticated": False, "user": None}
    return {
        "ok": True,
        "authenticated": True,
        "user": {
            "username": me["username"],
            "name": me.get("name") or "",
            "email": me.get("email") or "",
        },
    }


@app.get("/api/portfolio/positions")
async def get_portfolio_positions(request: Request) -> dict:
    user = _require_authentik_user(request)
    items = await asyncio.to_thread(list_positions, user)
    return {"ok": True, "items": items}


@app.put("/api/portfolio/positions")
async def put_portfolio_positions(request: Request, body: PortfolioPositionsBody) -> dict:
    user = _require_authentik_user(request)
    payload = [item.model_dump() for item in body.items]
    items = await asyncio.to_thread(replace_positions, user, payload)
    return {"ok": True, "items": items}


@app.post("/api/portfolio/positions/migrate")
async def migrate_portfolio_positions(request: Request, body: PortfolioPositionsBody) -> dict:
    """Một lần: localStorage → SQLite khi user chưa có dòng server."""
    user = _require_authentik_user(request)
    payload = [item.model_dump() for item in body.items]
    migrated, items = await asyncio.to_thread(migrate_if_empty, user, payload)
    return {"ok": True, "migrated": migrated, "items": items}


class ScreenerRequest(BaseModel):
    """Screen Redis snapshot (or optional inline rows) with composite rules."""

    mode: str = "and"
    include_index: bool = False
    rules: list[ScreenerRule] = Field(default_factory=list)
    volume_min: float | None = None
    change_pct_min: float | None = None
    change_pct_max: float | None = None
    flags: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] | None = None


@app.get("/api/screener/presets")
async def screener_presets() -> dict:
    return {"presets": PRESETS, "ops": sorted(["gte", "gt", "lte", "lt", "eq", "neq", "in", "contains"])}


@app.post("/api/screener")
async def screener_run(body: ScreenerRequest):
    raw_rules = [r.model_dump() for r in body.rules]
    invalid = find_invalid_raw_rules(raw_rules)
    if invalid:
        msg = "; ".join(invalid)
        log(COMPONENT, "SCREENER", msg, logging.WARNING, error_code=ERR_PB_SCREENER)
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error_code": ERR_PB_SCREENER, "message": msg},
        )

    compose_rules, _ = build_compose_rules(
        volume_min=body.volume_min,
        change_pct_min=body.change_pct_min,
        change_pct_max=body.change_pct_max,
        flags=body.flags,
    )
    merged = raw_rules + compose_rules
    engine = FilterEngine(merged, mode=body.mode, include_index=body.include_index)

    if body.rows is not None:
        source_rows = body.rows
        source = "inline"
    else:
        redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        try:
            source_rows = await load_snapshot(redis)
            source = "redis_hash"
        except Exception as exc:
            log(
                COMPONENT,
                "SCREENER",
                "redis snapshot load failed",
                logging.ERROR,
                error_code=ERR_PB_REDIS,
                exc=exc,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error_code": ERR_PB_REDIS,
                    "message": "Cannot load priceboard snapshot from Redis",
                },
            )
        finally:
            await redis.aclose()

    matched = engine.filter_rows(source_rows)
    log(
        COMPONENT,
        "SCREENER",
        "screener run complete",
        matched=len(matched),
        total=len(source_rows),
        mode=engine.mode,
        rules=len(engine.rules),
        source=source,
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
        while True:
            msg = await websocket.receive_text()
            if msg in ("ping", '{"type":"ping"}'):
                await manager.send_personal(websocket, '{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log(
            COMPONENT,
            "WS",
            "websocket handler error",
            logging.WARNING,
            error_code=ERR_PB_WS,
            exc=exc,
        )
    finally:
        await redis.aclose()
        await manager.disconnect(websocket)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
