"""Provider chỉ số theo thứ tự ưu tiên: SSI FastConnect (khi có key) -> Entrade -> Vietcap.

Mỗi provider: quotes(symbols) -> {sym: IdxQuote} (có thể thiếu mã), bars(symbols, since_epoch) -> {sym: [(epoch, close)]}.
Lỗi mạng/HTTP/định dạng -> ProviderDown. Parse tách thành hàm thuần (parse_*) để test bằng response mẫu.
"""
from __future__ import annotations

import time
from datetime import datetime

import requests

from ingestion.index.common import ERR_IDX_PARSE, FUTURES, IdxQuote, ProviderDown, log


class Provider:
    name = "BASE"

    def __init__(self, settings, session=None):
        self.s = settings
        ps = settings.provider_settings.get(self.name, {})
        self.timeout = float(ps.get("timeout", 5))
        self.http = session or requests.Session()
        self.http.headers.update({"User-Agent": settings.user_agent, "Accept": "application/json, text/plain, */*",
                                  "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"})

    @property
    def enabled(self) -> bool:
        return True

    def cost(self, symbols) -> int:
        return 1

    def _json(self, method: str, url: str, **kw):
        try:
            r = self.http.request(method, url, timeout=self.timeout, **kw)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            raise ProviderDown(f"{self.name} {type(e).__name__}: {str(e)[:160]}") from None

    def quotes(self, symbols) -> dict:
        raise NotImplementedError

    def bars(self, symbols, since: int) -> dict:
        raise NotImplementedError


def _parse_guard(name, fn, *a):
    try:
        return fn(*a)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        log("PARSE", f"{name} bad payload: {type(e).__name__}: {e}", error_code=ERR_IDX_PARSE, source=name)
        raise ProviderDown(f"{name} parse error") from None


# ------------------------------------------------------------------ Vietcap (trading.vietcap.com.vn)
VCI_INDEX = {"VNINDEX": "VNINDEX", "HNXINDEX": "HNXIndex", "UPCOMINDEX": "HNXUpcomIndex", "VN30": "VN30"}
VCI_BASE = "https://trading.vietcap.com.vn/api"


def parse_vci_market_index(payload) -> dict:
    rev = {v: k for k, v in VCI_INDEX.items()}
    out = {}
    for row in payload:
        sym = rev.get(row.get("symbol"))
        if sym and row.get("price") and row.get("refPrice"):
            out[sym] = IdxQuote(sym, float(row["price"]), float(row["refPrice"]), "VIETCAP", row.get("time"))
    return out


def parse_vci_futures(payload) -> tuple[dict, dict]:
    """symbols/getList -> ({VN30F1M: quote}, {VN30F1M: {'code': 41I1GB000, 'maturity': '2026-11-20'}})."""
    quotes, contracts = {}, {}
    for row in payload:
        li, mp = row.get("listingInfo") or {}, row.get("matchPrice") or {}
        alias = li.get("mappingSymbol")
        if alias not in FUTURES:
            continue
        mat = li.get("maturityDate")
        contracts[alias] = {"code": li["symbol"],
                            "maturity": datetime.strptime(mat, "%d/%m/%Y").date().isoformat() if mat else None}
        ref = mp.get("referencePrice") or li.get("refPrice")
        price = mp.get("matchPrice") or ref
        if price and ref:
            quotes[alias] = IdxQuote(alias, float(price), float(ref), "VIETCAP", mp.get("time"), li["symbol"])
    return quotes, contracts


def parse_vci_bars(payload, code_to_sym: dict) -> dict:
    out = {}
    for row in payload:
        sym = code_to_sym.get(row.get("symbol"))
        if sym:
            out[sym] = [(int(t), float(c)) for t, c in zip(row["t"], row["c"])]
    return out


class Vietcap(Provider):
    name = "VIETCAP"

    def __init__(self, settings, session=None):
        super().__init__(settings, session)
        self.http.headers.update({"Referer": "https://trading.vietcap.com.vn/", "Origin": "https://trading.vietcap.com.vn"})
        self.contracts: dict = {}   # VN30F1M -> {code, maturity}

    def cost(self, symbols) -> int:
        return int(any(s in VCI_INDEX for s in symbols)) + int(any(s in FUTURES for s in symbols))

    def resolve_futures(self) -> dict:
        group = self._json("GET", f"{VCI_BASE}/price/symbols/getByGroup", params={"group": "FU_INDEX"})
        codes = [g["symbol"] for g in group if str(g.get("symbol", "")).startswith("41I1")]
        if not codes:
            raise ProviderDown("VIETCAP no futures codes")
        _, contracts = _parse_guard(self.name, parse_vci_futures,
                                    self._json("POST", f"{VCI_BASE}/price/symbols/getList", json={"symbols": codes}))
        self.contracts = contracts
        return contracts

    def resolve_futures_wrapped(self, _symbols) -> dict:
        return self.resolve_futures()

    def quotes(self, symbols) -> dict:
        out = {}
        idx = [VCI_INDEX[s] for s in symbols if s in VCI_INDEX]
        if idx:
            out.update(_parse_guard(self.name, parse_vci_market_index,
                                    self._json("POST", f"{VCI_BASE}/price/marketIndex/getList", json={"symbols": idx})))
        futs = [s for s in symbols if s in FUTURES]
        if futs:
            if not all(f in self.contracts for f in futs):
                self.resolve_futures()
            codes = [self.contracts[f]["code"] for f in futs if f in self.contracts]
            q, c = _parse_guard(self.name, parse_vci_futures,
                                self._json("POST", f"{VCI_BASE}/price/symbols/getList", json={"symbols": codes}))
            out.update({k: v for k, v in q.items() if k in futs})
            self.contracts.update(c)
        return {k: v for k, v in out.items() if k in symbols}

    def bars(self, symbols, since: int) -> dict:
        code_to_sym = {VCI_INDEX[s]: s for s in symbols if s in VCI_INDEX}
        for f in symbols:
            if f in FUTURES:
                if f not in self.contracts:
                    self.resolve_futures()
                if f in self.contracts:
                    code_to_sym[self.contracts[f]["code"]] = f
        payload = self._json("POST", f"{VCI_BASE}/chart/OHLCChart/gap",
                             json={"timeFrame": "ONE_MINUTE", "symbols": list(code_to_sym), "from": since, "to": int(time.time())})
        return _parse_guard(self.name, parse_vci_bars, payload, code_to_sym)


# ------------------------------------------------------------------ Entrade (DNSE chart API)
ENT_BASE = "https://services.entrade.com.vn/chart-api/v2/ohlcs"
ENT_INDEX = {"VNINDEX": "VNINDEX", "HNXINDEX": "HNX", "UPCOMINDEX": "UPCOM", "VN30": "VN30"}


def parse_ent_bars(payload) -> list[tuple[int, float]]:
    return [(int(t), float(c)) for t, c in zip(payload["t"], payload["c"])]


def ent_ref_from_daily(payload, today_epoch_start: int) -> float | None:
    """Giá tham chiếu = close của phiên ngày gần nhất trước hôm nay."""
    prev = [(int(t), float(c)) for t, c in zip(payload["t"], payload["c"]) if int(t) < today_epoch_start]
    return prev[-1][1] if prev else None


class Entrade(Provider):
    name = "ENTRADE"

    def __init__(self, settings, session=None, clock=time.time):
        super().__init__(settings, session)
        self.http.headers.update({"Referer": "https://banggia.dnse.com.vn/", "Origin": "https://banggia.dnse.com.vn"})
        self.clock = clock
        self.refs: dict = {}   # (sym, date) -> ref

    def cost(self, symbols) -> int:
        return len(symbols) + sum(1 for s in symbols if not any(k[0] == s for k in self.refs))

    def _url(self, sym):
        return (f"{ENT_BASE}/derivative", sym) if sym in FUTURES else (f"{ENT_BASE}/index", ENT_INDEX[sym])

    def _get(self, sym, resolution, since):
        url, code = self._url(sym)
        return self._json("GET", url, params={"symbol": code, "resolution": resolution, "from": since, "to": int(self.clock())})

    def bars(self, symbols, since: int) -> dict:
        return {s: _parse_guard(self.name, parse_ent_bars, self._get(s, "1", since)) for s in symbols}

    def quotes(self, symbols) -> dict:
        from ingestion.index.series import session_start_epoch
        now = self.clock()
        out = {}
        for s in symbols:
            bars = _parse_guard(self.name, parse_ent_bars, self._get(s, "1", int(now) - 86400 * self.s.lookback_days))
            if not bars:
                continue
            last_t = bars[-1][0]
            day = session_start_epoch(last_t, self.s.timezone)
            key = (s, day)
            if key not in self.refs:
                daily = self._get(s, "1D", int(now) - 86400 * 15)
                self.refs[key] = _parse_guard(self.name, ent_ref_from_daily, daily, day)
            if self.refs[key]:
                out[s] = IdxQuote(s, bars[-1][1], self.refs[key], "ENTRADE",
                                  datetime.fromtimestamp(last_t).astimezone().isoformat())
        return out


# ------------------------------------------------------------------ SSI Developer Portal (api.ssi.com.vn v3)
# Docs: https://developers.ssi.com.vn/docs/getting-started/first-api-call
SSI_AUTH_URL = "https://api.ssi.com.vn/api/v3/auth/token"
SSI_DATA = "https://api.ssi.com.vn/api/v3/data"
# Chỉ số spot; phái sinh (VN30F*) để provider sau / WebSocket.
SSI_INDEX = {"VNINDEX", "HNXINDEX", "UPCOMINDEX", "VN30"}


def _ssi_token(body: dict) -> str | None:
    """Lấy access token từ vài shape response SSI (v3 auth / legacy FC)."""
    if not isinstance(body, dict):
        return None
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    for src in (body, data):
        for k in ("accessToken", "access_token", "token"):
            v = src.get(k)
            if v:
                return str(v)
    return None


def _ssi_rows(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data
    return []


def _ssi_parse_ts(raw: str) -> int | None:
    """Parse tradingDate SSI: 'YYYY/MM/DD HH:mm:ss' hoặc 'YYYY/MM/DD'."""
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    return None


class SSI(Provider):
    """REST SSI v3: auth + indexSummary + ohlc. Tắt khi thiếu SSI_CONSUMER_ID/SECRET.

    Env: SSI_CONSUMER_ID→apiKey, SSI_CONSUMER_SECRET→apiSecret. Private Key / OTP = Trading — không dùng.
    Rate-limit header quan sát: data ≈ 20/cửa sổ (refresh nhanh). WebSocket market = bước sau."""
    name = "SSI"

    def __init__(self, settings, session=None):
        super().__init__(settings, session)
        self.token, self.token_exp = None, 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.s.env.get("SSI_CONSUMER_ID") and self.s.env.get("SSI_CONSUMER_SECRET"))

    def cost(self, symbols) -> int:
        return len([s for s in symbols if s in SSI_INDEX]) + 1

    def _auth(self):
        if self.token and time.time() < self.token_exp:
            return
        j = self._json(
            "POST",
            SSI_AUTH_URL,
            json={
                "apiKey": self.s.env["SSI_CONSUMER_ID"],
                "apiSecret": self.s.env["SSI_CONSUMER_SECRET"],
            },
        )
        tok = _ssi_token(j)
        if not tok:
            raise ProviderDown(f"SSI auth failed status={j.get('status')} msg={j.get('message') or j.get('error')}")
        exp = j.get("expiresAt")
        try:
            exp_ts = float(exp) if exp is not None else time.time() + 6 * 3600
        except (TypeError, ValueError):
            exp_ts = time.time() + 6 * 3600
        self.token, self.token_exp = tok, max(time.time() + 60, exp_ts - 60)
        self.http.headers["Authorization"] = f"Bearer {tok}"

    def _today(self) -> str:
        return datetime.now().strftime("%Y/%m/%d")

    def quotes(self, symbols) -> dict:
        if not self.enabled:
            raise ProviderDown("SSI disabled (no credentials)")
        self._auth()
        out = {}
        day = self._today()
        for s in symbols:
            if s not in SSI_INDEX:
                continue
            j = self._json("GET", f"{SSI_DATA}/indexSummary", params={"index": s, "tradingDate": day})
            rows = _ssi_rows(j)
            if not rows:
                continue
            row = rows[-1]
            val = float(row["indexValue"])
            chg = float(row.get("indexChange") or 0)
            out[s] = IdxQuote(s, val, round(val - chg, 2), "SSI", row.get("tradingDate"))
        return out

    def bars(self, symbols, since: int) -> dict:
        if not self.enabled:
            raise ProviderDown("SSI disabled (no credentials)")
        self._auth()
        out = {}
        day = self._today()
        for s in symbols:
            if s not in SSI_INDEX:
                continue
            j = self._json(
                "GET",
                f"{SSI_DATA}/ohlc",
                params={
                    "symbol": s,
                    "from": f"{day} 00:00:00",
                    "to": f"{day} 23:59:59",
                    "timeFrame": "1m",
                    "pageIndex": 1,
                    "pageSize": 1000,
                },
            )
            pts = []
            for row in _ssi_rows(j):
                t = _ssi_parse_ts(row.get("tradingDate") or "")
                if t is None or t < since:
                    continue
                pts.append((t, float(row["close"])))
            out[s] = pts
        return out


REGISTRY = {"SSI": SSI, "ENTRADE": Entrade, "VIETCAP": Vietcap}
