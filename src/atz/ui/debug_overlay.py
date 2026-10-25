"""Lớp debug UI atz.vn: hotkey ⌘⇧D / Ctrl⇧D + chip hàng/cột bảng.

Kill-switch: config ``enabled: false`` hoặc env ``ATZ_DEBUG_OVERLAY=0``.
Chip bảng: ``table_deep: false`` để tắt riêng.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "debug_overlay.yaml"
_AGENT_DBG_LOG = repo_root() / ".cursor" / "debug-6352fb.log"


def _agent_dbg_log(message: str, *, hypothesis_id: str, data: dict | None = None) -> None:
    """NDJSON cho phiên debug Cursor (6352fb). Không log PII."""
    try:
        import json
        import time

        payload = {
            "sessionId": "6352fb",
            "timestamp": int(time.time() * 1000),
            "location": "debug_overlay.py",
            "message": message,
            "hypothesisId": hypothesis_id,
            "data": data or {},
        }
        _AGENT_DBG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _AGENT_DBG_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


_DBG_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ROW_KEY_COLS = ("Mã", "Ma", "symbol", "Symbol", "Thành phần", "ID")

_AUTO_REGIONS = (
    ("DBG-SIDEBAR", '[data-testid="stSidebar"]'),
    ("DBG-NAV", '[data-testid="stButtonGroup"]'),
    ("DBG-MAIN", '[data-testid="stMain"]'),
)


def sanitize_dbg_id(value: object) -> str:
    """Chỉ nhận id an toàn cho attribute HTML. Không hợp lệ → ''."""
    text = str(value or "").strip()
    if not _DBG_ID_RE.match(text):
        return ""
    return text


def sanitize_token(value: object, *, fallback: str = "x", max_len: int = 48) -> str:
    """Slug an toàn cho tên cột/hàng trong atz-dbg copy string."""
    text = str(value or "").strip()
    parts: list[str] = []
    for ch in text:
        if ch.isalnum() or ch in "_-":
            parts.append(ch)
        else:
            parts.append("_")
    slug = "".join(parts).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug[:max_len]
    return slug or fallback


def _env_tri_state(name: str) -> bool | None:
    raw = os.environ.get(name, "").strip().lower()
    if raw in ("0", "false", "off", "no"):
        return False
    if raw in ("1", "true", "on", "yes"):
        return True
    return None


def load_debug_config(path: Path | str | None = None) -> dict:
    """Đọc block debug_overlay. Thiếu file → tắt. Env ATZ_DEBUG_OVERLAY ghi đè enabled."""
    path = Path(path or DEFAULT_PATH)
    if not path.exists():
        base = {
            "enabled": False,
            "table_deep": False,
            "max_row_chips": 40,
            "allow_local": False,
            "allowed_groups": [],
            "storage_key": "atz-dbg-on",
            "atz_inspect_enabled": False,
            "require_admin_groups": False,
        }
    else:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        block = doc.get("debug_overlay") or {}
        groups = block.get("allowed_groups") or []
        if not isinstance(groups, list):
            groups = []
        key = str(block.get("storage_key") or "atz-dbg-on").strip() or "atz-dbg-on"
        if not re.match(r"^[A-Za-z0-9_-]+$", key):
            key = "atz-dbg-on"
        try:
            max_rows = int(block.get("max_row_chips", 40))
        except (TypeError, ValueError):
            max_rows = 40
        surfaces = block.get("surfaces") if isinstance(block.get("surfaces"), dict) else {}
        atz = surfaces.get("atz") if isinstance(surfaces.get("atz"), dict) else {}
        global_on = bool(block.get("enabled", False))
        atz_inspect = global_on and bool(atz.get("enabled", True)) and bool(atz.get("inspect", True))
        base = {
            "enabled": global_on,
            "table_deep": bool(block.get("table_deep", True)),
            "max_row_chips": max(1, min(200, max_rows)),
            "allow_local": bool(block.get("allow_local", False)),
            "allowed_groups": [str(g).strip() for g in groups if str(g).strip()],
            "storage_key": key,
            "atz_inspect_enabled": atz_inspect,
            "require_admin_groups": bool(block.get("require_admin_groups", False)),
        }
    env_on = _env_tri_state("ATZ_DEBUG_OVERLAY")
    if env_on is not None:
        base["enabled"] = env_on
    env_table = _env_tri_state("ATZ_DEBUG_TABLE_DEEP")
    if env_table is not None:
        base["table_deep"] = env_table
    return base


def user_may_use_debug(me: dict | None, config: dict | None = None) -> bool:
    """Gate: enabled + local / atz inspect surface (giống dev priceboard) hoặc giao groups."""
    config = config or load_debug_config()
    if not config.get("enabled"):
        return False
    if me is None:
        return bool(config.get("allow_local"))
    if config.get("atz_inspect_enabled") and not config.get("require_admin_groups"):
        return True
    allowed = {g.casefold() for g in config.get("allowed_groups") or []}
    if not allowed:
        return False
    user_groups = {str(g).strip().casefold() for g in (me.get("groups") or []) if str(g).strip()}
    return bool(user_groups & allowed)


def extract_row_keys(data: Any, *, max_rows: int = 40) -> list[str]:
    """Lấy khóa hàng từ cột Mã / Thành phần / ID; không có thì r0..rn."""
    import pandas as pd

    frame = getattr(data, "data", data)
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    limit = max(1, int(max_rows))
    for col in _ROW_KEY_COLS:
        if col not in frame.columns:
            continue
        out: list[str] = []
        seen: set[str] = set()
        for raw in frame[col].tolist():
            token = sanitize_token(str(raw).strip().upper() if col in ("Mã", "Ma", "symbol", "Symbol") else raw)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
            if len(out) >= limit:
                break
        if out:
            return out
    return [f"r{i}" for i in range(min(limit, len(frame)))]


def compose_dbg_ref(table: str, *, col: str | None = None, row: str | None = None) -> str:
    """Tạo chuỗi copy: atz-dbg:table[.col.X][.row.Y] hoặc .cell.ROW.COL."""
    table_id = sanitize_dbg_id(table) or sanitize_token(table, fallback="table")
    if row and col:
        return f"atz-dbg:{table_id}.cell.{sanitize_token(row)}.{sanitize_token(col)}"
    if col:
        return f"atz-dbg:{table_id}.col.{sanitize_token(col)}"
    if row:
        return f"atz-dbg:{table_id}.row.{sanitize_token(row)}"
    return f"atz-dbg:{table_id}"


def _pill(label: str, copy_text: str, *, pick: str | None = None, table: str | None = None) -> str:
    attrs = [
        f'data-atz-dbg-copy="{html.escape(copy_text, quote=True)}"',
        'class="atz-dbg-pill"',
        'type="button"',
    ]
    if pick and table:
        attrs.append(f'data-atz-dbg-pick="{html.escape(pick, quote=True)}"')
        attrs.append(f'data-atz-dbg-table="{html.escape(table, quote=True)}"')
    return f"<button {' '.join(attrs)}>{html.escape(label)}</button>"


def table_legend_html(
    table_key: str,
    columns: list[str],
    row_keys: list[str],
) -> str:
    """HTML legend (ẩn khi DBG OFF nhờ CSS body.atz-dbg-on)."""
    table_id = sanitize_dbg_id(table_key) or sanitize_token(table_key, fallback="table")
    col_pills = []
    for index, name in enumerate(columns):
        token = sanitize_token(name, fallback=f"c{index}")
        col_pills.append(
            _pill(
                f"COL:{name}",
                compose_dbg_ref(table_id, col=token),
                pick=f"col:{token}",
                table=table_id,
            )
        )
    row_pills = []
    for index, name in enumerate(row_keys):
        token = sanitize_token(name, fallback=f"r{index}")
        row_pills.append(
            _pill(
                f"ROW:{name}",
                compose_dbg_ref(table_id, row=token),
                pick=f"row:{token}",
                table=table_id,
            )
        )
    cell_btn = (
        f'<button type="button" class="atz-dbg-pill atz-dbg-cell-btn" '
        f'data-atz-dbg-table="{html.escape(table_id, quote=True)}" '
        f'data-atz-dbg-cell="1">Copy CELL (ROW+COL)</button>'
    )
    return (
        f'<div class="atz-dbg-table-legend" data-atz-dbg-table="{html.escape(table_id, quote=True)}">'
        f'<div class="atz-dbg-table-title">TABLE {html.escape(table_id)} · click COL/ROW · '
        f"chọn cả hai rồi CELL</div>"
        f'<div class="atz-dbg-table-row"><span class="atz-dbg-k">Cột</span> {"".join(col_pills) or "—"}</div>'
        f'<div class="atz-dbg-table-row"><span class="atz-dbg-k">Hàng</span> {"".join(row_pills) or "—"}</div>'
        f'<div class="atz-dbg-table-row">{cell_btn} '
        f'<span class="atz-dbg-pick-state" data-atz-dbg-state="{html.escape(table_id, quote=True)}">'
        f"chưa chọn</span></div>"
        f"</div>"
    )


def dbg_anchor(dbg_id: str) -> None:
    """Marker ẩn trước khối UI. JS gắn outline vào container nội dung kế bên."""
    code = sanitize_dbg_id(dbg_id)
    if not code:
        return
    try:
        import streamlit as st

        from engine.identity import current_me
    except Exception:
        return
    if not user_may_use_debug(current_me()):
        return
    safe = html.escape(code, quote=True)
    atd = html.escape(f"atz-ui:{code}", quote=True)
    st.html(
        f'<div data-atz-dbg="{safe}" data-atd-id="{atd}" class="atz-dbg-anchor" aria-hidden="true" '
        f'style="display:none;height:0;margin:0;padding:0;overflow:hidden"></div>'
    )




def dbg_breakdown_anchor(base_id: str, row_key: str, payload: Any) -> None:
    """Marker ẩn theo mã + JSON breakdown (Cố vấn / «Tại sao lọt top?»)."""
    import json

    code = sanitize_dbg_id(base_id)
    if not code:
        return
    row = sanitize_token(row_key, fallback="sym")
    full = f"{code}-{row}" if row else code
    if not _DBG_ID_RE.match(full):
        full = code
    try:
        import streamlit as st

        from engine.identity import current_me
    except Exception:
        return
    if not user_may_use_debug(current_me()):
        return
    safe = html.escape(full, quote=True)
    atd = html.escape(f"atz-ui:{full}", quote=True)
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    safe_blob = html.escape(blob, quote=True)
    st.html(
        f'<div data-atz-dbg="{safe}" data-atd-id="{atd}" data-atz-dbg-payload="{safe_blob}" '
        f'class="atz-dbg-anchor atz-dbg-breakdown" aria-hidden="true" '
        f'style="display:none;height:0;margin:0;padding:0;overflow:hidden"></div>'
    )


def dbg_table_legend(
    table_key: str,
    columns: list[str],
    row_keys: list[str] | None = None,
    *,
    data: Any = None,
) -> None:
    """Chip COL/ROW/CELL phía trên bảng — chỉ khi enabled + table_deep + user được phép."""
    config = load_debug_config()
    try:
        import streamlit as st

        from engine.identity import current_me
    except Exception:
        return
    if not user_may_use_debug(current_me(), config) or not config.get("table_deep"):
        return
    table_id = sanitize_dbg_id(table_key) or sanitize_token(table_key, fallback="")
    if not table_id:
        return
    rows = list(row_keys or [])
    if not rows and data is not None:
        rows = extract_row_keys(data, max_rows=int(config.get("max_row_chips") or 40))
    cols = [str(c) for c in columns if str(c).strip()]
    if not cols and not rows:
        return
    dbg_anchor(f"DBG-TBL-{table_id}")
    st.html(table_legend_html(table_id, cols, rows))


def _inspect_assets_html(storage_key: str) -> str:
    """Hybrid Inspect overlay (shared debug-overlay.js) — atz-ui:* refs."""
    sk = html.escape(storage_key, quote=True)
    return f"""
<script>
// #region agent log
(function(){{try{{fetch("http://127.0.0.1:7722/ingest/48452b2f-cc37-4967-87d2-94240ee9fe6c",{{method:"POST",headers:{{"Content-Type":"application/json","X-Debug-Session-Id":"6352fb"}},body:JSON.stringify({{sessionId:"6352fb",location:"debug_overlay:inline",message:"atz assets html injected",data:{{storageKey:"{sk}"}},timestamp:Date.now(),hypothesisId:"H1"}})}}).catch(function(){{}});}}catch(e){{}}}})();
// #endregion
</script>
<link rel="stylesheet" href="/static/debug-overlay.css">
<style>
  .atz-dbg-table-legend {{
    margin: 0.2rem 0 0.55rem; padding: 8px 10px;
    border: 1px dashed #64748b; border-radius: 8px;
    font: 11px/1.35 ui-monospace, monospace; color: #94a3b8;
  }}
  body.pb-dbg-on .atz-dbg-table-legend {{ display: none !important; }}
  .atz-dbg-table-title {{ margin-bottom: 6px; font-weight: 700; }}
  .atz-dbg-table-row {{ margin: 4px 0; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }}
  .atz-dbg-k {{ font-weight: 700; margin-right: 4px; min-width: 2.5rem; }}
  .atz-dbg-pill {{
    font: 10px/1.2 ui-monospace, monospace;
    background: #475569; color: #fff; border: 0; border-radius: 4px;
    padding: 3px 6px; cursor: copy;
  }}
  .atz-dbg-pill.is-pick {{ box-shadow: 0 0 0 2px #fff, 0 0 0 4px #334155; }}
</style>
<script src="/static/debug-overlay.js" defer
  data-storage-key="{sk}"
  data-catalog-url="/static/ui_catalog_atz.json"
  data-ref-prefix="atz-ui"
  data-surface="atz"></script>
"""


def inject_debug_overlay() -> None:
    """Gắn CSS/JS overlay nếu user được phép. Idempotent phía client."""
    try:
        import streamlit as st

        from engine.identity import current_me
    except Exception:
        return
    config = load_debug_config()
    me = current_me()
    may = user_may_use_debug(me, config)
    group_count = len(me.get("groups") or []) if me else 0
    _agent_dbg_log(
        "inject_debug_overlay",
        hypothesis_id="H1",
        data={
            "enabled": bool(config.get("enabled")),
            "may_use": may,
            "me_present": me is not None,
            "group_count": group_count,
            "allow_local": bool(config.get("allow_local")),
        },
    )
    if not may:
        return
    st.html(
        _inspect_assets_html(config["storage_key"]),
        unsafe_allow_javascript=True,
    )
