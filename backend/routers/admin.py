"""Admin control-plane + Admin-First ops config HTTP routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.admin_config_bus import publish_config_reload
from backend.admin_config_store import (
    get_control_plane,
    get_ops_config,
    put_control_plane,
    put_ops_config,
)


class AdminControlPlaneBody(BaseModel):
    """Nested stream_alerts/risk/priceboard plus flat CDP screening aliases."""

    model_config = ConfigDict(extra="ignore")

    stream_alerts: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    screening_filters: dict[str, Any] | None = None
    priceboard: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    # Flat aliases (also accepted at top level)
    rsi_length: float | None = None
    rsi_oversold: float | None = Field(default=None, ge=0, le=100)
    rsi_overbought: float | None = Field(default=None, ge=0, le=100)
    ma_fast_period: int | None = Field(default=None, ge=1, le=200)
    ma_slow_period: int | None = Field(default=None, ge=2, le=400)
    volume_spike_mult: float | None = Field(default=None, ge=0.5, le=20)
    volume_spike_lookback: int | None = Field(default=None, ge=2, le=200)


class AdminOpsConfigBody(BaseModel):
    """Admin-First ops payload for ``/api/admin/config``."""

    model_config = ConfigDict(extra="ignore")

    priceboard: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    core_allocation: dict[str, Any] | None = None
    max_core: int | None = None
    lookback_sessions: int | None = None
    force_vn30: bool | None = None
    min_volume: int | None = None
    min_volume_by_exchange: dict[str, Any] | None = None
    maintenance_mode: bool | None = None
    ondemand_sync_enabled: bool | None = None
    reload_core_on_save: bool | None = None


def register_admin_routes(
    app,
    *,
    require_admin: Callable[[Request], str],
    apply_stream_config: Callable[[dict[str, Any]], None],
) -> None:
    """Attach control-plane + ``/api/admin/config`` routes."""

    @app.get("/api/admin/control-plane")
    async def admin_get_control_plane(request: Request) -> dict:
        require_admin(request)
        return get_control_plane()

    async def _save_control_plane(request: Request, body: AdminControlPlaneBody) -> dict:
        require_admin(request)
        try:
            result = put_control_plane(body.model_dump(exclude_none=False))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stream = result.get("stream_alerts") or {}
        apply_stream_config(stream if isinstance(stream, dict) else {})
        pb = result.get("priceboard") if isinstance(result.get("priceboard"), dict) else None
        await publish_config_reload(
            stream if isinstance(stream, dict) else None,
            priceboard=pb,
        )
        return result

    @app.put("/api/admin/control-plane")
    async def admin_put_control_plane(request: Request, body: AdminControlPlaneBody) -> dict:
        return await _save_control_plane(request, body)

    @app.post("/api/admin/control-plane")
    async def admin_post_control_plane(request: Request, body: AdminControlPlaneBody) -> dict:
        return await _save_control_plane(request, body)

    @app.get("/api/admin/config")
    async def admin_get_config(request: Request) -> dict:
        """Admin-First ops config (Core allocation, volume gates, flags)."""
        require_admin(request)
        return get_ops_config()

    @app.post("/api/admin/config")
    async def admin_post_config(request: Request, body: AdminOpsConfigBody) -> dict:
        require_admin(request)
        try:
            result = put_ops_config(body.model_dump(exclude_none=True))
        except ValueError as exc:
            # Soft fallback: return safe defaults instead of crashing
            safe = get_ops_config()
            safe["ok"] = False
            safe["error"] = str(exc)
            safe["warnings"] = list(safe.get("warnings") or []) + [f"save failed: {exc}"]
            return safe
        pb = result.get("config") if isinstance(result.get("config"), dict) else None
        await publish_config_reload(priceboard=pb)
        return result

    @app.put("/api/admin/config")
    async def admin_put_config(request: Request, body: AdminOpsConfigBody) -> dict:
        return await admin_post_config(request, body)
