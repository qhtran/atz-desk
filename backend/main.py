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

from backend.core.database import init_db
from backend.index_spark import load_index_spark
from backend.market_db import init_market_db
from backend.core.errors import AppError, app_error_handler
from backend.core.logging_middleware import TraceMiddleware
from backend.debug_ui import public_debug_ui_config
from backend.portfolio_alerts import position_alert
from backend.identity import me_from_headers
from backend.portfolio_f3 import batch_f3_alerts, load_f3_sector_themes
from backend.portfolio_quotes import normalize_symbols, resolve_portfolio_quotes
from backend.daily_signals import ALLOWED_FILTERS, scan_daily_signals
from backend.equity_spark import load_equity_intraday, load_equity_spark
from backend.symbol_analysis import chart_limit_from_query, load_bars_for_chart, scan_filter_markers
from backend.portfolio_store import list_positions, migrate_if_empty, replace_positions
from backend.observability import ERR_PB_REDIS, ERR_PB_SCREENER, ERR_PB_WS, log, setup
from backend.modules.trading.router import router as trading_router
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
    init_db()
    init_market_db()
    listener.start()
    log(COMPONENT, "API-START", "priceboard api started", frontend=str(FRONTEND_DIR), redis_url=REDIS_URL)
    yield
    await listener.stop()
    log(COMPONENT, "API-STOP", "priceboard api stopped")


app = FastAPI(title="atz priceboard", version="0.1.0-dev", lifespan=lifespan)
app.add_middleware(TraceMiddleware)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(trading_router)


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


class DailySignalsRequest(BaseModel):
    market: str = "HOSE"
    filter: str = Field(default="rsi", alias="filter")
    filters: list[str] | None = Field(default=None, alias="filters")
    combine: str = Field(default="and", alias="combine")
    buy_min_total: float | None = Field(default=None, ge=0, le=100)

    model_config = {"populate_by_name": True}


@app.get("/api/iboard/index-spark")
async def iboard_index_spark(symbols: str | None = None) -> dict:
    """Intraday 1m series for index-bar spark (SQLite + Redis cache)."""
    sym_list = None
    if symbols and symbols.strip():
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        return await load_index_spark(redis, symbols=sym_list)
    finally:
        await redis.aclose()


@app.get("/api/iboard/equity-spark")
async def iboard_equity_spark(symbols: str | None = None) -> dict:
    """Bulk 1m series for iBoard XHT column (same contract shape as index-spark)."""
    sym_list: list[str] = []
    if symbols and symbols.strip():
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        return await load_equity_spark(redis, symbols=sym_list)
    finally:
        await redis.aclose()


@app.get("/api/iboard/daily-signals/filters")
async def iboard_daily_signal_filters() -> dict:
    return {"ok": True, "filters": sorted(ALLOWED_FILTERS)}


@app.post("/api/iboard/daily-signals")
async def iboard_daily_signals(body: DailySignalsRequest) -> dict:
    """Quét OHLCV — subset mã match filter (iBoard chế độ Tín hiệu ngày)."""
    active = body.filters if body.filters else [body.filter]
    hits, scanned, matched = await asyncio.to_thread(
        scan_daily_signals,
        market=body.market,
        filter_name=body.filter,
        filters=body.filters,
        combine=body.combine,
        buy_min_total=body.buy_min_total,
    )
    return {
        "ok": True,
        "symbols": [h["symbol"] for h in hits],
        "hits": hits,
        "scanned": scanned,
        "matched": matched,
        "filter": active[0] if len(active) == 1 else ",".join(active),
        "filters": active,
        "combine": body.combine,
        "market": body.market.upper(),
    }


@app.get("/api/iboard/symbol-bars")
async def iboard_symbol_bars(
    symbol: str,
    limit: int = 252,
    range: str | None = None,
) -> dict:
    """OHLCV daily cho chart phân tích mã (preset range 1m–5y)."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol required")
    cap = chart_limit_from_query(range_key=range, limit=limit)
    bars = await asyncio.to_thread(load_bars_for_chart, sym, limit=cap)
    return {"ok": True, "symbol": sym, "range": (range or "").strip().lower() or None, "limit": cap, "bars": bars}


@app.get("/api/iboard/symbol-intraday")
async def iboard_symbol_intraday(symbol: str, trading_date: str | None = None) -> dict:
    """Intraday 1m phiên VN cho preset chart 1d."""
    sym = str(symbol or "").strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol required")
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        return await load_equity_intraday(redis, sym, trading_date=trading_date)
    finally:
        await redis.aclose()


@app.get("/api/iboard/symbol-filter-history")
async def iboard_symbol_filter_history(
    symbol: str,
    filter: str,
    limit: int = 252,
    range: str | None = None,
    buy_min_total: float | None = None,
) -> dict:
    """Marker lịch sử một filter trên mã."""
    sym = str(symbol or "").strip().upper()
    name = str(filter or "").strip().lower()
    if not sym or not name:
        raise HTTPException(status_code=400, detail="symbol and filter required")
    cap = chart_limit_from_query(range_key=range, limit=limit)
    payload = await asyncio.to_thread(
        scan_filter_markers,
        sym,
        name,
        limit=cap,
        buy_min_total=buy_min_total,
    )
    if not payload.get("ok"):
        return payload
    return payload


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


@app.get("/trading")
async def trading_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "trading.html")


if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
