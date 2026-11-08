"""Session facts for morning brief — full-auto, no Admin paste.

Sources (best-effort, never crash cron):
1. OHLCV bars → VNINDEX close / ±điểm / ±%
2. Redis priceboard → NN ròng (foreignNetValue) + GTGD ước lượng (last×volume)
3. vnstock Insights (optional, nếu có trong runtime) → NN + tự doanh tổng HOSE

Mọi field thiếu → null + note rõ nguồn; Mode 1/2 không bịa số.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from backend.portfolio_f3 import load_symbol_bars

logger = logging.getLogger("morning_brief_facts")

TZ_NAME = "Asia/Ho_Chi_Minh"
TY_DONG = 1_000_000_000.0  # 1 tỷ VNĐ


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _fmt_tn(value: float | None, *, digits: int = 1) -> str | None:
    if value is None:
        return None
    return f"{value:.{digits}f}"


def vni_from_bars(bars_dir: Path, symbol: str = "VNINDEX") -> dict[str, Any]:
    """Đóng cửa / ±điểm / ±% từ OHLCV CSV."""
    out: dict[str, Any] = {
        "symbol": str(symbol or "VNINDEX").upper(),
        "close": None,
        "prev_close": None,
        "chg_pts": None,
        "chg_pct": None,
        "direction": None,
        "source": "ohlcv_missing",
    }
    bars = load_symbol_bars(out["symbol"], bars_dir)
    if bars is None or bars.empty:
        return out
    lookup = {str(c).lower(): c for c in bars.columns}
    if "close" not in lookup:
        return out
    close = pd.to_numeric(bars[lookup["close"]], errors="coerce").dropna()
    if len(close) < 2:
        if len(close) == 1:
            out["close"] = round(float(close.iloc[-1]), 2)
            out["source"] = "ohlcv"
        return out
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg = last - prev
    pct = (chg / prev * 100.0) if prev else 0.0
    direction = "tăng" if chg > 0 else ("giảm" if chg < 0 else "đi ngang")
    out.update(
        {
            "close": round(last, 2),
            "prev_close": round(prev, 2),
            "chg_pts": round(chg, 2),
            "chg_pct": round(pct, 2),
            "direction": direction,
            "source": "ohlcv",
        }
    )
    return out


def _parse_quote_payload(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


def collect_redis_board_stats(
    *,
    redis_url: str | None = None,
    hash_key: str | None = None,
    redis_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Quét priceboard Redis: NN ròng + GTGD ước lượng (Σ last×volume)."""
    import redis as redis_lib

    url = redis_url or os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
    hkey = hash_key or os.getenv("PRICEBOARD_HASH", "priceboard:quotes")
    result: dict[str, Any] = {
        "nn_net_vnd": None,
        "gtgd_vnd": None,
        "equity_count": 0,
        "nn_count": 0,
        "source": "redis_unavailable",
        "error": None,
    }
    client = None
    try:
        factory = redis_factory or redis_lib.from_url
        client = factory(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
        raw_map = client.hgetall(hkey) or {}
    except Exception as exc:  # noqa: BLE001 — best-effort collector
        result["error"] = str(exc)[:120]
        return result
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    nn_sum = 0.0
    nn_n = 0
    gtgd_sum = 0.0
    eq_n = 0
    for _sym, payload in raw_map.items():
        tick = _parse_quote_payload(payload)
        if not tick:
            continue
        kind = str(tick.get("kind") or "").lower()
        if kind == "index":
            continue
        last = _as_float(tick.get("last"))
        vol = _as_float(tick.get("volume"))
        if last is not None and vol is not None and last > 0 and vol > 0:
            # tick_contract equity: last = VNĐ nguyên; volume = KL khớp → GTGD ≈ Σ last×vol
            gtgd_sum += last * vol
            eq_n += 1
        fnet = _as_float(tick.get("foreignNetValue"))
        if fnet is None:
            buy_v = _as_float(tick.get("foreignBuyValue"))
            sell_v = _as_float(tick.get("foreignSellValue"))
            if buy_v is not None or sell_v is not None:
                fnet = float(buy_v or 0) - float(sell_v or 0)
        if fnet is not None:
            nn_sum += fnet
            nn_n += 1

    result["equity_count"] = eq_n
    result["nn_count"] = nn_n
    if eq_n > 0:
        result["gtgd_vnd"] = gtgd_sum
        result["source"] = "redis_board"
    if nn_n > 0:
        result["nn_net_vnd"] = nn_sum
        result["source"] = "redis_board"
    if eq_n == 0 and nn_n == 0:
        result["source"] = "redis_empty"
    return result


def collect_vnstock_flows() -> dict[str, Any]:
    """Optional vnstock Insights — NN + tự doanh tổng HOSE (value_1d)."""
    out: dict[str, Any] = {
        "nn_net_vnd": None,
        "prop_net_vnd": None,
        "source": "vnstock_unavailable",
        "error": None,
    }
    try:
        from vnstock import Insights  # type: ignore
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"import: {exc}"[:120]
        return out

    try:
        ins = Insights()
        foreign = ins.flow.foreign(exchange="HOSE", group_by="stock")
        prop = ins.flow.proprietary(exchange="HOSE", group_by="stock")
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:160]
        out["source"] = "vnstock_error"
        logger.warning("ERR-BRIEF-040: vnstock flow failed: %s", exc)
        return out

    def _sum_value_1d(frame: Any) -> float | None:
        if frame is None:
            return None
        try:
            if hasattr(frame, "empty") and frame.empty:
                return None
            col = None
            for name in ("value_1d", "Value_1D", "net_val"):
                if hasattr(frame, "columns") and name in frame.columns:
                    col = name
                    break
            if col is None:
                return None
            series = pd.to_numeric(frame[col], errors="coerce").dropna()
            if series.empty:
                return None
            return float(series.sum())
        except Exception:
            return None

    nn = _sum_value_1d(foreign)
    prop_v = _sum_value_1d(prop)
    if nn is not None:
        out["nn_net_vnd"] = nn
    if prop_v is not None:
        out["prop_net_vnd"] = prop_v
    if nn is not None or prop_v is not None:
        out["source"] = "vnstock_insights"
    else:
        out["source"] = "vnstock_empty"
    return out


def _tf_sentence(label: str, phrase: str | None) -> str:
    text = str(phrase or "").strip() or "thiếu tín hiệu F3"
    return f"{label}: {text}."


def build_session_facts(
    *,
    bars_dir: Path,
    index_symbol: str = "VNINDEX",
    index_tech: dict[str, Any] | None = None,
    redis_url: str | None = None,
    hash_key: str | None = None,
    enable_vnstock: bool | None = None,
    redis_factory: Callable[..., Any] | None = None,
    vnstock_collector: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gom facts phiên tại thời điểm soạn tin."""
    as_of = datetime.now().astimezone().isoformat(timespec="seconds")
    use_vnstock = (
        enable_vnstock
        if enable_vnstock is not None
        else os.getenv("BRIEF_ENABLE_VNSTOCK", "1").strip() not in ("0", "false", "no")
    )

    vni = vni_from_bars(bars_dir, index_symbol)
    redis_stats = collect_redis_board_stats(
        redis_url=redis_url,
        hash_key=hash_key,
        redis_factory=redis_factory,
    )
    vn_flows = (
        (vnstock_collector or collect_vnstock_flows)()
        if use_vnstock
        else {"nn_net_vnd": None, "prop_net_vnd": None, "source": "vnstock_skipped"}
    )

    # Ưu tiên vnstock cho NN/tự doanh; Redis bổ sung / fallback NN + GTGD.
    nn_vnd = vn_flows.get("nn_net_vnd")
    nn_src = "vnstock" if nn_vnd is not None else None
    if nn_vnd is None and redis_stats.get("nn_net_vnd") is not None:
        nn_vnd = redis_stats["nn_net_vnd"]
        nn_src = "redis"

    prop_vnd = vn_flows.get("prop_net_vnd")
    prop_src = "vnstock" if prop_vnd is not None else None

    gtgd_vnd = redis_stats.get("gtgd_vnd")
    gtgd_src = "redis_est" if gtgd_vnd is not None else None

    nn_tn = round(float(nn_vnd) / TY_DONG, 1) if nn_vnd is not None else None
    prop_tn = round(float(prop_vnd) / TY_DONG, 1) if prop_vnd is not None else None
    gtgd_tn = round(float(gtgd_vnd) / TY_DONG, 1) if gtgd_vnd is not None else None

    tech = index_tech or {}
    tf = {
        "M": tech.get("M"),
        "W": tech.get("W"),
        "D": tech.get("D"),
    }

    # Session summary (Hiến-style bullets) — chỉ số có thật.
    close = vni.get("close")
    chg_pts = vni.get("chg_pts")
    chg_pct = vni.get("chg_pct")
    direction = vni.get("direction") or "đi ngang"
    if close is not None and chg_pts is not None:
        session_line = (
            f"Kết thúc phiên gần nhất, {vni['symbol']} đạt {close:g} "
            f"{direction} {abs(float(chg_pts)):g} điểm"
            + (f" ({chg_pct:+.2f}%)" if chg_pct is not None else "")
            + "."
        )
    else:
        session_line = f"{vni['symbol']}: thiếu OHLCV — chưa đủ số liệu phiên."

    if gtgd_tn is not None:
        # Hiến hay viết «15.8k tỷ» (= nghìn tỷ). ≥1000 tỷ → dạng k tỷ.
        if abs(gtgd_tn) >= 1000:
            liq_disp = f"{gtgd_tn / 1000.0:.1f}k tỷ"
        else:
            liq_disp = f"{_fmt_tn(gtgd_tn)} tỷ"
        liquidity_line = (
            f"Giá trị giao dịch ước lượng ≈ {liq_disp} đồng "
            f"(Σ last×volume board; nguồn={gtgd_src})."
        )
    else:
        liquidity_line = "GTGD: thiếu dữ liệu board Redis — bỏ qua, không bịa."

    parts_flow: list[str] = []
    if nn_tn is not None:
        side = "mua ròng" if nn_tn > 0 else ("bán ròng" if nn_tn < 0 else "cân bằng")
        parts_flow.append(f"NN {side} {abs(nn_tn):.1f} tỷ (nguồn={nn_src})")
    else:
        parts_flow.append("NN: thiếu dữ liệu — bỏ qua")
    if prop_tn is not None:
        side_p = "mua ròng" if prop_tn > 0 else ("bán ròng" if prop_tn < 0 else "cân bằng")
        parts_flow.append(f"tự doanh {side_p} {abs(prop_tn):.1f} tỷ (nguồn={prop_src})")
    else:
        parts_flow.append("tự doanh: thiếu dữ liệu (cần vnstock Insights) — bỏ qua")
    foreign_prop_line = "Dòng tiền lớn: " + "; ".join(parts_flow) + "."

    narratives = {
        "M": _tf_sentence("Khung tháng", tf.get("M")),
        "W": _tf_sentence("Khung tuần", tf.get("W")),
        "D": _tf_sentence("Khung ngày", tf.get("D")),
    }

    # Kế hoạch đơn giản từ D phrase / hướng VNI.
    plan = "Quan sát"
    d_phrase = str(tf.get("D") or "").lower()
    if "thủng" in d_phrase or "cắt" in d_phrase:
        plan = "Quan sát / phòng thủ"
    elif direction == "tăng" and "trên mây" in d_phrase:
        plan = "Quan sát — giữ nhịp, tránh FOMO"

    forecast = (
        f"Dự báo ngắn: VNI nghiêng {direction}"
        + (f" ({chg_pct:+.2f}%)" if chg_pct is not None else "")
        + " theo tín hiệu khung ngày; quản trị rủi ro tuyệt đối."
    )

    return {
        "as_of": as_of,
        "vni": vni,
        "gtgd_tn": gtgd_tn,
        "nn_net_tn": nn_tn,
        "prop_net_tn": prop_tn,
        "index_tf": tf,
        "tf_narratives": narratives,
        "session_line": session_line,
        "liquidity_line": liquidity_line,
        "foreign_prop_line": foreign_prop_line,
        "forecast_line": forecast,
        "plan": plan,
        "sources": {
            "vni": vni.get("source"),
            "gtgd": gtgd_src,
            "nn": nn_src,
            "prop": prop_src,
            "redis": redis_stats.get("source"),
            "vnstock": vn_flows.get("source"),
            "redis_error": redis_stats.get("error"),
            "vnstock_error": vn_flows.get("error"),
        },
    }


def format_facts_macro_block(facts: dict[str, Any]) -> str:
    """Khối text Mode 1 (nhận định) từ facts — không Gemini."""
    lines = [
        facts.get("session_line") or "",
        facts.get("liquidity_line") or "",
        facts.get("foreign_prop_line") or "",
        "",
        "### Khung Tháng (M)",
        (facts.get("tf_narratives") or {}).get("M") or "—",
        "",
        "### Khung Tuần (W)",
        (facts.get("tf_narratives") or {}).get("W") or "—",
        "",
        "### Khung Ngày (D)",
        (facts.get("tf_narratives") or {}).get("D") or "—",
        "",
        facts.get("forecast_line") or "",
        f"Kế hoạch giao dịch: {facts.get('plan') or 'Quan sát'}",
    ]
    return "\n".join(line for line in lines if line is not None)
