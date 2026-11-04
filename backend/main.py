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
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.authentik_ropc import (
    MfaRequired,
    RopcAuthError,
    RopcConfigError,
    mfa_grant,
    password_grant,
    ropc_configured,
)
from backend.core.database import init_db
from backend.index_spark import load_index_spark
from backend.market_db import init_market_db
from backend.core.errors import AppError, app_error_handler
from backend.core.logging_middleware import TraceMiddleware
from backend.debug_ui import public_debug_ui_config
from backend.portfolio_alerts import position_alert
from backend.account_config import load_account_config
from backend.desk_session import COOKIE_NAME as DESK_COOKIE, desk_session_enabled, issue_session_value
from backend.identity import is_admin_user, resolve_me, roles_for_user
from backend.portfolio_f3 import batch_f3_alerts, load_f3_sector_themes
from backend.portfolio_quotes import normalize_symbols, resolve_portfolio_quotes
from backend.daily_signals import ALLOWED_FILTERS, scan_daily_signals
from backend.equity_spark import load_equity_intraday, load_equity_spark
from backend.symbol_analysis import chart_limit_from_query, load_bars_for_chart, scan_filter_markers
from backend.portfolio_store import list_positions, migrate_if_empty, replace_positions
from backend.observability import ERR_PB_REDIS, ERR_PB_SCREENER, ERR_PB_WS, log, setup
from backend.modules.trading.router import router as trading_router
from backend.engine.stream_listener import QuantStreamListener
from backend.redis_listener import HASH_KEY, REDIS_URL, RedisTickListener, load_snapshot
from backend.screener import PRESETS, FilterEngine, build_compose_rules, find_invalid_raw_rules
from backend.websocket_manager import ConnectionManager
from backend.routers.admin import register_admin_routes
from backend.routers.alerts_ws import register_alerts_ws_alias
from backend.desk_alerts_store import init_desk_alerts_store
from backend.routers.desk_alerts import router as desk_alerts_router
from backend.routers.watchlist import router as watchlist_router
from backend.watchlist_store import init_watchlist_store
from backend.ws_alerts import register_alerts_ws

setup("api")
COMPONENT = "api"

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parent.parent / "frontend"))

manager = ConnectionManager()
listener = RedisTickListener(manager)
alert_manager = ConnectionManager()
stream_listener = QuantStreamListener(alert_manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    init_market_db()
    init_watchlist_store()
    init_desk_alerts_store()
    listener.start()
    stream_listener.start()
    log(COMPONENT, "API-START", "priceboard api started", frontend=str(FRONTEND_DIR), redis_url=REDIS_URL)
    yield
    await stream_listener.stop()
    await listener.stop()
    log(COMPONENT, "API-STOP", "priceboard api stopped")


app = FastAPI(title="atz priceboard", version="0.1.0-dev", lifespan=lifespan)
app.add_middleware(TraceMiddleware)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(trading_router)
app.include_router(watchlist_router)
app.include_router(desk_alerts_router)
register_alerts_ws(app, alert_manager)
register_alerts_ws_alias(app, alert_manager)


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
        "alert_clients": alert_manager.client_count,
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


def _resolve_request_me(request: Request) -> dict[str, Any] | None:
    return resolve_me(request.headers, desk_cookie=request.cookies.get(DESK_COOKIE))


def _require_authentik_user(request: Request) -> str:
    me = _resolve_request_me(request)
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    return str(me["username"])


def _require_admin(request: Request) -> str:
    """401 nếu chưa login; 403 nếu không thuộc admin_groups / superuser."""
    me = _resolve_request_me(request)
    if not me or not me.get("username"):
        raise HTTPException(status_code=401, detail="Authentik login required")
    cfg = load_account_config()
    admin = is_admin_user(list(me.get("groups") or []), cfg.get("admin_groups")) or bool(
        me.get("is_superuser")
    )
    if not admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return str(me["username"])


def _account_payload(me: dict[str, Any] | None, cfg: dict[str, Any]) -> dict[str, Any]:
    from backend.core.trading_config import risk_meta_for_user

    auth_urls = {
        "login_url": cfg.get("login_url") or "",
        "logout_url": cfg.get("logout_url") or "",
        "password_flow_url": cfg.get("password_flow_url") or "",
        "mfa_flow_url": cfg.get("mfa_flow_url") or "",
        "desk_session_form": bool(cfg.get("desk_session_form")),
    }
    if not me:
        return {
            "ok": True,
            "authenticated": False,
            "user": None,
            "groups": [],
            "roles": [],
            "is_admin": False,
            "auth_source": None,
            "risk_meta": risk_meta_for_user(None),
            **auth_urls,
        }
    groups = list(me.get("groups") or [])
    admin = is_admin_user(groups, cfg.get("admin_groups")) or bool(me.get("is_superuser"))
    roles = roles_for_user(groups, is_admin=admin)
    return {
        "ok": True,
        "authenticated": True,
        "user": {
            "username": me["username"],
            "name": me.get("name") or "",
            "email": me.get("email") or "",
            "groups": groups,
            "roles": roles,
            "is_admin": admin,
        },
        "groups": groups,
        "roles": roles,
        "is_admin": admin,
        "auth_source": me.get("source") or "forward_auth",
        "risk_meta": risk_meta_for_user(me["username"]),
        **auth_urls,
    }


class DeskLoginBody(BaseModel):
    """Pha 1: username+password. Pha 2 MFA: mfa_token+code."""

    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=256)
    mfa_token: str | None = Field(default=None, max_length=128)
    code: str | None = Field(default=None, max_length=16)


def _issue_desk_cookie(response: Response, profile: dict[str, Any]) -> dict[str, Any]:
    token = issue_session_value(
        username=profile["username"],
        email=profile.get("email") or "",
        name=profile.get("name") or "",
        uid=profile.get("uid") or "",
        groups=list(profile.get("groups") or []),
        is_superuser=bool(profile.get("is_superuser")),
    )
    secure = (os.getenv("DESK_SESSION_SECURE") or "1").strip() not in ("0", "false", "no")
    response.set_cookie(
        key=DESK_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int(os.getenv("DESK_SESSION_TTL_SEC") or 12 * 3600),
    )
    cfg = load_account_config()
    me = {
        "username": profile["username"],
        "email": profile.get("email") or "",
        "name": profile.get("name") or "",
        "uid": profile.get("uid") or "",
        "groups": list(profile.get("groups") or []),
        "source": "desk_session",
    }
    return {"success": True, **_account_payload(me, cfg)}


register_admin_routes(
    app,
    require_admin=_require_admin,
    apply_stream_config=stream_listener.apply_config,
)


@app.post("/api/auth/login", response_model=None)
async def desk_auth_login(body: DeskLoginBody, response: Response):
    """DEV headless login: Authentik Flow (+ optional TOTP) → ``atz_desk_session``."""
    if not desk_session_enabled() or not ropc_configured():
        raise HTTPException(status_code=503, detail="Desk session login disabled on this host")

    mfa_token = (body.mfa_token or "").strip()
    code = (body.code or "").strip()
    username = (body.username or "").strip()
    password = body.password or ""

    try:
        if mfa_token or code:
            if not mfa_token or not code:
                raise HTTPException(status_code=400, detail="Thiếu mfa_token hoặc mã OTP")
            profile = await asyncio.to_thread(mfa_grant, mfa_token, code)
            return _issue_desk_cookie(response, profile)

        if not username or not password:
            raise HTTPException(status_code=400, detail="Nhập tài khoản và mật khẩu")
        profile = await asyncio.to_thread(password_grant, username, password)
        return _issue_desk_cookie(response, profile)
    except MfaRequired as exc:
        return JSONResponse(
            status_code=202,
            content={
                "success": False,
                "mfa_required": True,
                "mfa_token": exc.mfa_token,
                "detail": "Nhập mã xác thực (TOTP)",
            },
        )
    except HTTPException:
        raise
    except RopcConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RopcAuthError as exc:
        msg = str(exc.args[0] if exc.args else "")
        if msg in {"invalid otp", "mfa expired"}:
            detail = "Sai hoặc hết hạn mã OTP" if msg == "invalid otp" else "Phiên MFA hết hạn — đăng nhập lại"
            raise HTTPException(status_code=401, detail=detail) from None
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu") from None
    except Exception as exc:
        log(COMPONENT, "AUTH-LOGIN", "desk login failed", logging.WARNING, exc=exc)
        raise HTTPException(status_code=502, detail="Authentik login failed") from exc


@app.post("/api/auth/logout")
async def desk_auth_logout(response: Response) -> dict:
    """Xóa cookie desk session (DEV). Outpost logout vẫn dùng logout_url nếu cần."""
    response.delete_cookie(DESK_COOKIE, path="/")
    return {"ok": True, "success": True}


@app.get("/api/account/me")
async def account_me(request: Request) -> dict:
    """Identity: ForwardAuth headers hoặc desk session cookie + risk + RBAC SPA."""
    cfg = load_account_config()
    me = _resolve_request_me(request)
    return _account_payload(me, cfg)


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
async def iboard_daily_signals(request: Request, body: DailySignalsRequest) -> dict:
    """Quét OHLCV — subset mã match filter (iBoard chế độ Tín hiệu ngày)."""
    from backend.core.trading_config import risk_meta_for_user

    me = _resolve_request_me(request)
    username = me["username"] if me else None
    active = body.filters if body.filters else [body.filter]
    hits, scanned, matched = await asyncio.to_thread(
        scan_daily_signals,
        market=body.market,
        filter_name=body.filter,
        filters=body.filters,
        combine=body.combine,
        buy_min_total=body.buy_min_total,
        username=username,
    )
    risk_meta = risk_meta_for_user(username)
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
        "risk_meta": risk_meta,
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
