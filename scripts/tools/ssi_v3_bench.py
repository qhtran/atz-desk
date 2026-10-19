"""One-shot SSI v3 latency / options / rate-limit probe. No secrets printed."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request
from urllib.parse import urlencode

ENV_PATH = Path("/opt/vnstocks/.env")


def load_ssi_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.startswith("SSI_"):
            env[k] = v.strip().strip("\"'")
    return env


def http(method, url, headers=None, body=None, params=None, timeout=20):
    if params:
        url = url + "?" + urlencode(params)
    data = None if body is None else json.dumps(body).encode()
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "atz-bench",
    }
    if headers:
        h.update(headers)
    req = request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ms = (time.perf_counter() - t0) * 1000
            rh = {}
            for k, v in r.headers.items():
                if "rate" in k.lower() or "limit" in k.lower() or "retry" in k.lower():
                    rh[k] = v
            try:
                j = json.loads(raw.decode())
            except Exception:
                j = {"_raw_len": len(raw)}
            return r.status, j, ms, rh
    except error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        ms = (time.perf_counter() - t0) * 1000
        rh = {}
        for k, v in e.headers.items():
            if "rate" in k.lower() or "limit" in k.lower() or "retry" in k.lower():
                rh[k] = v
        try:
            j = json.loads(raw)
        except Exception:
            j = {"_raw": raw[:160]}
        return e.code, j, ms, rh


def pct(xs, p):
    xs = sorted(xs)
    i = max(0, min(len(xs) - 1, int(round((p / 100) * (len(xs) - 1)))))
    return xs[i]


def bench(name, fn, n=20):
    ok = fail = 0
    times = []
    last_rh = None
    last_st = None
    for _ in range(n):
        st, j, ms, rh = fn()
        times.append(ms)
        last_rh = rh or last_rh
        last_st = st
        if 200 <= st < 300:
            ok += 1
        else:
            fail += 1
    print(
        f"{name}: n={n} ok={ok} fail={fail} "
        f"p50={pct(times, 50):.0f} p95={pct(times, 95):.0f} "
        f"min={min(times):.0f} max={max(times):.0f} last_st={last_st} rl={last_rh}",
        flush=True,
    )


def main():
    env = load_ssi_env()
    st, body, ms, rh = http(
        "POST",
        "https://api.ssi.com.vn/api/v3/auth/token",
        body={"apiKey": env["SSI_CONSUMER_ID"], "apiSecret": env["SSI_CONSUMER_SECRET"]},
    )
    assert st == 200 and body.get("accessToken"), (st, body)
    tok = body["accessToken"]
    auth_h = {"Authorization": "Bearer " + tok}
    print("AUTH", round(ms), "ms", "rl", rh, flush=True)

    today = datetime.now().strftime("%Y/%m/%d")
    idx_list = ["VNINDEX", "VN30", "HNXINDEX", "UPCOMINDEX"]
    syms = [
        "SSI", "VNM", "FPT", "HPG", "VCB", "MWG", "TCB", "MBB", "ACB", "VHM",
        "VIC", "VRE", "MSN", "GAS", "PLX", "SAB", "BID", "CTG", "LPB", "STB",
        "TPB", "VPB", "SHB", "EIB", "SSB", "BCM", "GVR", "KDH", "NLG", "DXG",
    ]

    bench(
        "SSI indexSummary VNINDEX",
        lambda: http(
            "GET",
            "https://api.ssi.com.vn/api/v3/data/indexSummary",
            headers=auth_h,
            params={"index": "VNINDEX", "tradingDate": today},
        ),
        n=30,
    )

    def four_indices():
        t0 = time.perf_counter()
        last_rh = {}
        last_st = 200
        for i in idx_list:
            st, j, ms, rh = http(
                "GET",
                "https://api.ssi.com.vn/api/v3/data/indexSummary",
                headers=auth_h,
                params={"index": i, "tradingDate": today},
            )
            last_rh = rh or last_rh
            last_st = st
            if st != 200:
                return st, j, (time.perf_counter() - t0) * 1000, last_rh
        return last_st, {"ok": 4}, (time.perf_counter() - t0) * 1000, last_rh

    bench("SSI indexSummary x4 serial wall", four_indices, n=10)

    bench(
        "SSI ohlc VNINDEX 1m",
        lambda: http(
            "GET",
            "https://api.ssi.com.vn/api/v3/data/ohlc",
            headers=auth_h,
            params={
                "symbol": "VNINDEX",
                "from": today + " 00:00:00",
                "to": today + " 23:59:59",
                "timeFrame": "1m",
                "pageIndex": 1,
                "pageSize": 5,
            },
        ),
        n=20,
    )

    bench(
        "SSI securitiesSummary 1sym",
        lambda: http(
            "GET",
            "https://api.ssi.com.vn/api/v3/data/securitiesSummary",
            headers=auth_h,
            params={"symbol": "SSI", "from": today, "to": today, "pageNumber": 1, "pageSize": 1},
        ),
        n=30,
    )

    bench(
        "SSI securitiesByBoard HOSE",
        lambda: http(
            "GET",
            "https://api.ssi.com.vn/api/v3/data/securitiesByBoard",
            headers=auth_h,
            params={"board": "HOSE"},
        ),
        n=5,
    )

    for n in (1, 10, 30, 50):
        t0 = time.perf_counter()
        ok = fail = 0
        last_rh = {}
        last_st = 200
        hit429 = False
        for s in (syms * 2)[:n]:
            st, j, ms, rh = http(
                "GET",
                "https://api.ssi.com.vn/api/v3/data/securitiesSummary",
                headers=auth_h,
                params={"symbol": s, "from": today, "to": today, "pageNumber": 1, "pageSize": 1},
            )
            last_rh = rh or last_rh
            last_st = st
            if 200 <= st < 300:
                ok += 1
            else:
                fail += 1
            if st in (429, 403, 401):
                hit429 = True
                break
        wall = (time.perf_counter() - t0) * 1000
        print(
            f"SSI securitiesSummary batch n={n}: wall_ms={wall:.0f} ok={ok} fail={fail} "
            f"st={last_st} hit_limit={hit429} rl={last_rh} per_sym={wall / max(ok + fail, 1):.0f}",
            flush=True,
        )

    print("--- ramp to find HTTP limit (max 200) ---", flush=True)
    t_ramp = time.perf_counter()
    err = None
    last_rh = {}
    for i in range(1, 201):
        st, j, ms, rh = http(
            "GET",
            "https://api.ssi.com.vn/api/v3/data/securitiesSummary",
            headers=auth_h,
            params={
                "symbol": syms[i % len(syms)],
                "from": today,
                "to": today,
                "pageNumber": 1,
                "pageSize": 1,
            },
        )
        last_rh = rh or last_rh
        if i in (25, 50, 75, 100, 150, 200) or st != 200:
            print(f"  ramp i={i} st={st} ms={ms:.0f} rl={rh}", flush=True)
        if st != 200:
            err = (st, j, rh, i)
            break
    print(
        f"ramp done wall={(time.perf_counter() - t_ramp) * 1000:.0f}ms err={err} last_rl={last_rh}",
        flush=True,
    )

    print("--- options coverage smoke ---", flush=True)
    endpoints = [
        ("indexList", "https://api.ssi.com.vn/api/v3/data/indexList", {}),
        ("indexSummary", "https://api.ssi.com.vn/api/v3/data/indexSummary", {"index": "VNINDEX", "tradingDate": today}),
        ("securitiesByBoard", "https://api.ssi.com.vn/api/v3/data/securitiesByBoard", {"board": "HOSE"}),
        ("securitiesSummary", "https://api.ssi.com.vn/api/v3/data/securitiesSummary", {"symbol": "SSI", "from": today, "to": today}),
        ("ohlc_1d", "https://api.ssi.com.vn/api/v3/data/ohlc", {"symbol": "SSI", "from": "2026/10/01", "to": today, "timeFrame": "1d", "pageIndex": 1, "pageSize": 3}),
        ("ohlc_1m", "https://api.ssi.com.vn/api/v3/data/ohlc", {"symbol": "SSI", "from": today + " 09:00:00", "to": today + " 15:00:00", "timeFrame": "1m", "pageIndex": 1, "pageSize": 3}),
    ]
    for name, url, params in endpoints:
        st, j, ms, rh = http("GET", url, headers=auth_h, params=params)
        if isinstance(j, list):
            shape = f"list n={len(j)}"
        elif isinstance(j, dict):
            shape = f"dict keys={sorted(j.keys())[:6]}"
        else:
            shape = type(j).__name__
        print(f"  {name}: HTTP {st} ms={ms:.0f} {shape}", flush=True)

    print("--- vnstock KBS/VCI compare in container ---", flush=True)
    code = r"""
import time
from vnstock import Vnstock

def one(src, n):
    syms = ["SSI","VNM","FPT","HPG","VCB","MWG","TCB","MBB","ACB","VHM",
            "VIC","VRE","MSN","GAS","PLX","SAB","BID","CTG","LPB","STB",
            "TPB","VPB","SHB","EIB","SSB","BCM","GVR","KDH","NLG","DXG"][:n]
    t0 = time.perf_counter()
    try:
        st = Vnstock().stock(symbol=syms[0], source=src)
        df = st.trading.price_board(syms)
        ms = (time.perf_counter() - t0) * 1000
        print(f"vnstock {src} price_board n={n} ms={ms:.0f} rows={0 if df is None else len(df)}", flush=True)
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        print(f"vnstock {src} n={n} FAIL {type(e).__name__}: {str(e)[:140]} ms={ms:.0f}", flush=True)

for src in ("kbs", "vci"):
    for n in (1, 30):
        one(src, n)
"""
    Path("/tmp/atz_vnstock_bench.py").write_text(code)
    try:
        out = subprocess.check_output(
            [
                "docker", "run", "--rm", "--network", "vnstocks_realtime",
                "-v", "/tmp/atz_vnstock_bench.py:/bench.py:ro",
                "-e", "PYTHONUNBUFFERED=1",
                "vnstocks-vnstocks", "python", "/bench.py",
            ],
            text=True,
            timeout=180,
            stderr=subprocess.STDOUT,
        )
        print(out, flush=True)
    except Exception as e:
        print("vnstock_bench_fail", type(e).__name__, str(e)[:300], flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
