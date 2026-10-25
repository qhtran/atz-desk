"""SSI REST bootstrap for priceboard — last session close when WS is idle (off-hours).

Uses Market Data v3: indexSummary + securitiesSummary (developers.ssi.com.vn).
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from backend.board_universe import FUTURES_SYMBOL_SET, INDEX_BOARD_SYMBOLS, exchange_for_symbol
from backend.observability import ERR_PB_SSI_AUTH, log, setup
from backend.tick_contract import build_tick, tick_kind_for_symbol

setup("ssi_rest")
COMPONENT = "ssi_rest"

TZ_VN = timezone(timedelta(hours=7))
DEFAULT_DATA_BASE = "https://api.ssi.com.vn/api/v3/data"


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _vnd_price(value: float | None, *, symbol: str) -> float | None:
    """Equity REST often returns price in nghìn đồng; index/HĐTL giữ nguyên."""
    if value is None:
        return None
    v = float(value)
    if v <= 0:
        return v
    sym = str(symbol).upper()
    kind = tick_kind_for_symbol(sym)
    if kind == "index" or sym in FUTURES_SYMBOL_SET:
        return v
    if v < 500:
        return round(v * 1000)
    return v


def last_trading_date_vn(clock: datetime | None = None) -> str:
    """YYYY/MM/DD — lùi về T2–T6 gần nhất (dùng khi cuối tuần / trước phiên)."""
    now = clock or datetime.now(TZ_VN)
    d = now.date()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y/%m/%d")


def needs_rest_bootstrap(tick: dict[str, Any] | None) -> bool:
    """True when hash row missing or has no displayable last/ref."""
    if not tick:
        return True
    last = float(tick.get("last") or 0)
    ref = float(tick.get("ref") or 0)
    return last <= 0 and ref <= 0


class SsiRestClient:
    """Thin SSI data REST client (Bearer token supplied by caller)."""

    def __init__(
        self,
        token: str,
        *,
        data_base: str = DEFAULT_DATA_BASE,
        session: requests.Session | None = None,
        timeout: float = 25.0,
    ) -> None:
        self._token = token.strip()
        self._data_base = data_base.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self._data_base}/{path.lstrip('/')}?{urlencode(params)}"
        r = self._session.get(url, headers=self._headers(), timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            if isinstance(data, dict):
                return [data]
        return []

    def fetch_index_summary(self, index: str, trading_date: str) -> dict[str, Any] | None:
        try:
            payload = self._get_json(
                "indexSummary",
                {"index": index.upper(), "tradingDate": trading_date},
            )
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "REST-INDEX-ERR",
                "indexSummary failed",
                logging.WARNING,
                error_code=ERR_PB_SSI_AUTH,
                index=index,
                exc=exc,
            )
            return None
        rows = self._rows(payload)
        if not rows:
            return None
        row = rows[0]
        for key in ("index", "indexCode", "Indexcode"):
            if str(row.get(key) or "").upper() == index.upper():
                return row
        return rows[0]

    def fetch_securities_summary(self, symbol: str, trading_date: str) -> dict[str, Any] | None:
        try:
            payload = self._get_json(
                "securitiesSummary",
                {
                    "symbol": symbol.upper(),
                    "from": trading_date,
                    "to": trading_date,
                    "pageIndex": 1,
                    "pageSize": 1,
                },
            )
        except Exception as exc:  # noqa: BLE001
            log(
                COMPONENT,
                "REST-EQ-ERR",
                "securitiesSummary failed",
                logging.WARNING,
                error_code=ERR_PB_SSI_AUTH,
                symbol=symbol,
                exc=exc,
            )
            return None
        rows = self._rows(payload)
        return rows[0] if rows else None


def index_tick_from_summary(row: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    sym = str(symbol).strip().upper()
    last = _num(row.get("indexValue"))
    if last is None:
        return None
    change = _num(row.get("indexChange"))
    change_pct = _num(row.get("indexChangePercentage") or row.get("indexChangePercent"))
    ref = round(last - change, 6) if change is not None else last
    volume = _num(row.get("totalMatch") or row.get("totalTrade"))
    return build_tick(
        symbol=sym,
        last=last,
        ref=ref,
        kind=tick_kind_for_symbol(sym),
        exchange=exchange_for_symbol(sym),
        volume=int(volume or 0),
        change=change,
        change_pct=change_pct,
        source="SSI_REST",
        extra={"bootstrap": "indexSummary", "tradingDate": row.get("tradingDate")},
    )


def equity_tick_from_summary(row: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    sym = str(symbol).strip().upper()
    last_raw = _num(row.get("close"))
    if last_raw is None:
        return None
    last = _vnd_price(last_raw, symbol=sym)
    if last is None or last <= 0:
        return None
    change_raw = _num(row.get("priceChange"))
    change = _vnd_price(change_raw, symbol=sym) if change_raw is not None else None
    change_pct = _num(row.get("priceChangePercentage"))
    ref_raw = _num(row.get("average") or row.get("open"))
    ref = _vnd_price(ref_raw, symbol=sym) if ref_raw is not None else None
    if ref is None and change is not None:
        ref = round(float(last) - float(change), 6)
    if ref is None:
        ref = last
    high = _vnd_price(_num(row.get("high")), symbol=sym)
    low = _vnd_price(_num(row.get("low")), symbol=sym)
    vol = _num(row.get("totalMatch") or row.get("totalTrade"))
    fb = _num(row.get("totalForeignBuy"))
    fs = _num(row.get("totalForeignSell"))
    fbv = _num(row.get("totalForeignBuyValue"))
    fsv = _num(row.get("totalForeignSellValue"))
    return build_tick(
        symbol=sym,
        last=last,
        ref=ref,
        kind="equity",
        exchange=exchange_for_symbol(sym),
        volume=int(vol or 0),
        high=high,
        low=low,
        change=change,
        change_pct=change_pct,
        foreignBuy=int(fb) if fb is not None else None,
        foreignSell=int(fs) if fs is not None else None,
        foreignBuyValue=int(fbv) if fbv is not None else None,
        foreignSellValue=int(fsv) if fsv is not None else None,
        source="SSI_REST",
        extra={"bootstrap": "securitiesSummary", "tradingDate": row.get("tradingDate")},
    )


def bootstrap_ticks(
    client: SsiRestClient,
    *,
    index_symbols: list[str] | None = None,
    equity_symbols: list[str] | None = None,
    trading_date: str | None = None,
    sleep_between_equity: float = 0.12,
    clock: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch REST closes for symbols that need bootstrap."""
    td = trading_date or last_trading_date_vn(clock)
    indexes = list(index_symbols or INDEX_BOARD_SYMBOLS)
    equities = list(equity_symbols or [])
    out: list[dict[str, Any]] = []

    for sym in indexes:
        row = client.fetch_index_summary(sym, td)
        if not row:
            continue
        tick = index_tick_from_summary(row, sym)
        if tick:
            out.append(tick)

    for sym in equities:
        if tick_kind_for_symbol(sym) == "index" and sym in INDEX_BOARD_SYMBOLS:
            continue
        row = client.fetch_securities_summary(sym, td)
        if not row:
            time.sleep(sleep_between_equity)
            continue
        tick = equity_tick_from_summary(row, sym)
        if tick:
            out.append(tick)
        time.sleep(sleep_between_equity)

    return out
