"""Lớp debug UI atz.vn: hotkey ⌘⇧D / Ctrl⇧D + chip hàng/cột bảng.

Kill-switch: config ``enabled: false`` hoặc env ``ATZ_DEBUG_OVERLAY=0``.
Chip bảng: ``table_deep: false`` để tắt riêng.
"""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "debug_overlay.yaml"
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
        base = {
            "enabled": bool(block.get("enabled", False)),
            "table_deep": bool(block.get("table_deep", True)),
            "max_row_chips": max(1, min(200, max_rows)),
            "allow_local": bool(block.get("allow_local", False)),
            "allowed_groups": [str(g).strip() for g in groups if str(g).strip()],
            "storage_key": key,
        }
    env_on = _env_tri_state("ATZ_DEBUG_OVERLAY")
    if env_on is not None:
        base["enabled"] = env_on
    env_table = _env_tri_state("ATZ_DEBUG_TABLE_DEEP")
    if env_table is not None:
        base["table_deep"] = env_table
    return base


def user_may_use_debug(me: dict | None, config: dict | None = None) -> bool:
    """Gate: enabled + (local được phép khi me is None) hoặc giao groups."""
    config = config or load_debug_config()
    if not config.get("enabled"):
        return False
    if me is None:
        return bool(config.get("allow_local"))
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
    st.html(
        f'<div data-atz-dbg="{safe}" class="atz-dbg-anchor" aria-hidden="true" '
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


def _overlay_html(storage_key: str) -> str:
    auto_json = json.dumps(
        [{"id": dbg_id, "sel": sel} for dbg_id, sel in _AUTO_REGIONS],
        ensure_ascii=True,
    )
    return f"""
<style>
  .atz-dbg-badge {{
    position: fixed; right: 12px; bottom: 12px; z-index: 2147483000;
    font: 12px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #c2410c; color: #fff; padding: 8px 12px; border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,.28); display: none; pointer-events: auto;
    max-width: min(320px, 92vw);
  }}
  body.atz-dbg-on .atz-dbg-badge {{ display: block; }}
  body.atz-dbg-on [data-atz-dbg-bound="1"] {{
    outline: 2px dashed #ea580c !important;
    outline-offset: 2px;
    position: relative;
  }}
  .atz-dbg-chip {{
    position: absolute; top: 2px; left: 2px; z-index: 2147483001;
    font: 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #ea580c; color: #fff; padding: 2px 6px; border-radius: 4px;
    cursor: copy; user-select: none; white-space: nowrap;
    box-shadow: 0 1px 4px rgba(0,0,0,.25);
  }}
  .atz-dbg-chip:hover {{ background: #9a3412; }}
  .atz-dbg-toast {{
    position: fixed; left: 50%; bottom: 56px; transform: translateX(-50%);
    z-index: 2147483002; background: #14532d; color: #fff;
    font: 12px/1.3 system-ui, sans-serif; padding: 6px 12px; border-radius: 6px;
    display: none;
  }}
  .atz-dbg-table-legend {{
    display: none; margin: 0.2rem 0 0.55rem; padding: 8px 10px;
    border: 1px dashed #ea580c; border-radius: 8px; background: rgba(234,88,12,.10);
    font: 11px/1.35 ui-monospace, SFMono-Regular, Menlo, monospace; color: #9a3412;
  }}
  body.atz-dbg-on .atz-dbg-table-legend {{ display: block !important; }}
  .atz-dbg-table-title {{ margin-bottom: 6px; font-weight: 700; }}
  .atz-dbg-table-row {{ margin: 4px 0; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }}
  .atz-dbg-k {{ font-weight: 700; margin-right: 4px; min-width: 2.5rem; }}
  .atz-dbg-pill {{
    font: 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #ea580c; color: #fff; border: 0; border-radius: 4px;
    padding: 3px 6px; cursor: copy; max-width: 100%;
  }}
  .atz-dbg-pill:hover {{ background: #9a3412; }}
  .atz-dbg-pill.is-pick {{ box-shadow: 0 0 0 2px #fff, 0 0 0 4px #c2410c; }}
  .atz-dbg-pick-state {{ opacity: 0.85; }}
</style>
<div class="atz-dbg-badge" id="atz-dbg-badge" aria-live="polite">
  DBG ON · ⌘⇧D / Ctrl⇧D · Esc tắt<br/>
  Khối + chip COL/ROW/CELL · copy <code>atz-dbg:…</code><br/>
  Tắt hệ thống: env <code>ATZ_DEBUG_OVERLAY=0</code>
</div>
<div class="atz-dbg-toast" id="atz-dbg-toast"></div>
<script>
(function () {{
  var STORAGE = {json.dumps(storage_key)};
  var AUTO = {auto_json};
  var root = document;
  var picks = window.__atzDbgPicks || (window.__atzDbgPicks = {{}});
  (function dedupe(id) {{
    var nodes = document.querySelectorAll("#" + id);
    for (var i = 0; i < nodes.length - 1; i++) nodes[i].remove();
  }})("atz-dbg-badge");
  (function dedupe(id) {{
    var nodes = document.querySelectorAll("#" + id);
    for (var i = 0; i < nodes.length - 1; i++) nodes[i].remove();
  }})("atz-dbg-toast");
  function ensureApi() {{
    if (window.__atzDbg) return window.__atzDbg;
    var api = {{
      on: false,
      refresh: function () {{ applyLabels(); syncBadge(); }},
      setOn: function (v) {{
        api.on = !!v;
        try {{ sessionStorage.setItem(STORAGE, api.on ? "1" : "0"); }} catch (e) {{}}
        document.body.classList.toggle("atz-dbg-on", api.on);
        if (!api.on) clearLabels();
        else applyLabels();
        syncBadge();
      }},
      toggle: function () {{ api.setOn(!api.on); }}
    }};
    window.__atzDbg = api;
    return api;
  }}
  function toast(msg) {{
    var el = document.getElementById("atz-dbg-toast");
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
    clearTimeout(el._t);
    el._t = setTimeout(function () {{ el.style.display = "none"; }}, 1400);
  }}
  function copyText(text) {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).then(function () {{ toast("Đã copy " + text); }});
    }} else {{ toast(text); }}
  }}
  function syncBadge() {{
    var b = document.getElementById("atz-dbg-badge");
    if (b) b.style.display = ensureApi().on ? "block" : "none";
  }}
  function clearLabels() {{
    root.querySelectorAll("[data-atz-dbg-bound]").forEach(function (el) {{
      el.removeAttribute("data-atz-dbg-bound");
      el.removeAttribute("data-atz-dbg-id");
      var chip = el.querySelector(":scope > .atz-dbg-chip");
      if (chip) chip.remove();
    }});
  }}
  function resolveTarget(anchor) {{
    var box = anchor.closest('[data-testid="stElementContainer"]') || anchor.parentElement;
    if (!box) return anchor;
    var n = box.nextElementSibling;
    while (n) {{
      if (n.getAttribute && n.getAttribute("data-testid") === "stElementContainer") return n;
      n = n.nextElementSibling;
    }}
    return box;
  }}
  function bindTarget(target, id) {{
    if (!target || !id) return;
    if (target.getAttribute("data-atz-dbg-bound") === "1") return;
    target.setAttribute("data-atz-dbg-bound", "1");
    target.setAttribute("data-atz-dbg-id", id);
    var style = window.getComputedStyle(target);
    if (style.position === "static") target.style.position = "relative";
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "atz-dbg-chip";
    chip.textContent = id;
    chip.title = "Copy atz-dbg:" + id;
    chip.addEventListener("click", function (ev) {{
      ev.preventDefault();
      ev.stopPropagation();
      copyText("atz-dbg:" + id);
    }});
    target.appendChild(chip);
  }}
  function applyLabels() {{
    if (!ensureApi().on) return;
    clearLabels();
    root.querySelectorAll("[data-atz-dbg]").forEach(function (anchor) {{
      var id = anchor.getAttribute("data-atz-dbg");
      if (!id) return;
      bindTarget(resolveTarget(anchor), id);
    }});
    AUTO.forEach(function (item) {{
      var el = root.querySelector(item.sel);
      if (el) bindTarget(el, item.id);
    }});
  }}
  function syncPickUi(table) {{
    var st = picks[table] || {{}};
    root.querySelectorAll('[data-atz-dbg-state="' + table + '"]').forEach(function (el) {{
      el.textContent = "ROW=" + (st.row || "—") + " · COL=" + (st.col || "—");
    }});
    root.querySelectorAll('[data-atz-dbg-table="' + table + '"][data-atz-dbg-pick]').forEach(function (btn) {{
      var pick = btn.getAttribute("data-atz-dbg-pick") || "";
      var on = (pick === "row:" + st.row) || (pick === "col:" + st.col);
      btn.classList.toggle("is-pick", !!on);
    }});
  }}
  function onDocClick(ev) {{
    if (!ensureApi().on) return;
    var cellBtn = ev.target.closest("[data-atz-dbg-cell]");
    if (cellBtn) {{
      ev.preventDefault();
      ev.stopPropagation();
      var t = cellBtn.getAttribute("data-atz-dbg-table");
      var st = picks[t] || {{}};
      if (st.row && st.col) copyText("atz-dbg:" + t + ".cell." + st.row + "." + st.col);
      else toast("Chọn ROW và COL trước");
      return;
    }}
    var pickBtn = ev.target.closest("[data-atz-dbg-pick]");
    if (pickBtn) {{
      ev.preventDefault();
      ev.stopPropagation();
      var table = pickBtn.getAttribute("data-atz-dbg-table");
      var pick = pickBtn.getAttribute("data-atz-dbg-pick") || "";
      picks[table] = picks[table] || {{}};
      if (pick.indexOf("row:") === 0) picks[table].row = pick.slice(4);
      if (pick.indexOf("col:") === 0) picks[table].col = pick.slice(4);
      syncPickUi(table);
      var copy = pickBtn.getAttribute("data-atz-dbg-copy");
      if (copy) copyText(copy);
      var st2 = picks[table];
      if (st2.row && st2.col) toast("Đủ ROW+COL — bấm Copy CELL");
      return;
    }}
    var copyBtn = ev.target.closest("[data-atz-dbg-copy]");
    if (copyBtn && !copyBtn.getAttribute("data-atz-dbg-pick")) {{
      ev.preventDefault();
      ev.stopPropagation();
      var text = copyBtn.getAttribute("data-atz-dbg-copy");
      if (text) copyText(text);
    }}
  }}
  function onKey(ev) {{
    var key = (ev.key || "").toLowerCase();
    if (key === "escape" && ensureApi().on) {{
      ensureApi().setOn(false);
      toast("DBG OFF");
      return;
    }}
    if (key === "d" && ev.shiftKey && (ev.metaKey || ev.ctrlKey)) {{
      ev.preventDefault();
      ensureApi().toggle();
      toast(ensureApi().on ? "DBG ON" : "DBG OFF");
    }}
  }}
  var api = ensureApi();
  try {{ api.on = sessionStorage.getItem(STORAGE) === "1"; }} catch (e) {{ api.on = false; }}
  document.body.classList.toggle("atz-dbg-on", api.on);
  if (!window.__atzDbgKeyBound) {{
    window.addEventListener("keydown", onKey, true);
    window.__atzDbgKeyBound = true;
  }}
  if (!window.__atzDbgClickBound) {{
    document.addEventListener("click", onDocClick, true);
    window.__atzDbgClickBound = true;
  }}
  if (!window.__atzDbgObserver) {{
    var obs = new MutationObserver(function () {{
      if (ensureApi().on) {{
        clearTimeout(window.__atzDbgRefreshT);
        window.__atzDbgRefreshT = setTimeout(function () {{ applyLabels(); }}, 120);
      }}
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
    window.__atzDbgObserver = obs;
  }}
  applyLabels();
  syncBadge();
}})();
</script>
"""


def inject_debug_overlay() -> None:
    """Gắn CSS/JS overlay nếu user được phép. Idempotent phía client."""
    try:
        import streamlit as st

        from engine.identity import current_me
    except Exception:
        return
    config = load_debug_config()
    if not user_may_use_debug(current_me(), config):
        return
    st.html(
        _overlay_html(config["storage_key"]),
        unsafe_allow_javascript=True,
    )
