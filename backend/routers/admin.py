"""Admin control-plane HTTP routes (dev.atz.vn).

Flat screening filter aliases + PUT/POST save with Redis config-reload publish.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.admin_config_bus import publish_config_reload
from backend.admin_config_store import get_control_plane, put_control_plane


class AdminControlPlaneBody(BaseModel):
    """Nested stream_alerts/risk plus flat CDP screening aliases."""

    model_config = ConfigDict(extra="ignore")

    stream_alerts: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    screening_filters: dict[str, Any] | None = None
    # Flat aliases (also accepted at top level)
    rsi_length: float | None = None
    rsi_oversold: float | None = Field(default=None, ge=0, le=100)
    rsi_overbought: float | None = Field(default=None, ge=0, le=100)
    ma_fast_period: int | None = Field(default=None, ge=1, le=200)
    ma_slow_period: int | None = Field(default=None, ge=2, le=400)
    volume_spike_mult: float | None = Field(default=None, ge=0.5, le=20)
    volume_spike_lookback: int | None = Field(default=None, ge=2, le=200)
    min_traded_value: dict[str, Any] | None = None


def register_admin_routes(
    app,
    *,
    require_admin: Callable[[Request], str],
    apply_stream_config: Callable[[dict[str, Any]], None],
) -> None:
    """Attach GET/PUT/POST ``/api/admin/control-plane``."""

    @app.get("/api/admin/control-plane")
    async def admin_get_control_plane(request: Request) -> dict:
        require_admin(request)
        return get_control_plane()

    async def _save(request: Request, body: AdminControlPlaneBody) -> dict:
        require_admin(request)
        try:
            result = put_control_plane(body.model_dump(exclude_none=False))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stream = result.get("stream_alerts") or {}
        apply_stream_config(stream if isinstance(stream, dict) else {})
        floors = result.get("min_traded_value") if isinstance(result.get("min_traded_value"), dict) else None
        await publish_config_reload(stream if isinstance(stream, dict) else None, min_traded_value=floors)
        return result

    @app.put("/api/admin/control-plane")
    async def admin_put_control_plane(request: Request, body: AdminControlPlaneBody) -> dict:
        """Cập nhật overlay + in-process apply + Redis config-reload publish."""
        return await _save(request, body)

    @app.post("/api/admin/control-plane")
    async def admin_post_control_plane(request: Request, body: AdminControlPlaneBody) -> dict:
        """Alias of PUT for CDP clients that prefer POST."""
        return await _save(request, body)
