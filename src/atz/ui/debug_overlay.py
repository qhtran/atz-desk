"""Lớp debug UI atz.vn: hotkey ⌘⇧D / Ctrl⇧D gắn nhãn vùng (DBG-*).

Chỉ inject khi config bật và user được phép. Không gửi mạng; trạng thái giữ ở sessionStorage.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import yaml

from storage.paths import repo_root

DEFAULT_PATH = repo_root() / "config" / "debug_overlay.yaml"
_DBG_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

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


def load_debug_config(path: Path | str | None = None) -> dict:
    """Đọc block debug_overlay. Thiếu file → tắt."""
    path = Path(path or DEFAULT_PATH)
    if not path.exists():
        return {
            "enabled": False,
            "allow_local": False,
            "allowed_groups": [],
            "storage_key": "atz-dbg-on",
        }
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = doc.get("debug_overlay") or {}
    groups = block.get("allowed_groups") or []
    if not isinstance(groups, list):
        groups = []
    key = str(block.get("storage_key") or "atz-dbg-on").strip() or "atz-dbg-on"
    if not re.match(r"^[A-Za-z0-9_-]+$", key):
        key = "atz-dbg-on"
    return {
        "enabled": bool(block.get("enabled", False)),
        "allow_local": bool(block.get("allow_local", False)),
        "allowed_groups": [str(g).strip() for g in groups if str(g).strip()],
        "storage_key": key,
    }


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


def _overlay_html(storage_key: str) -> str:
    import json

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
    max-width: min(280px, 90vw);
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
</style>
<div class="atz-dbg-badge" id="atz-dbg-badge" aria-live="polite">
  DBG ON · ⌘⇧D / Ctrl⇧D · Esc tắt<br/>
  Click nhãn để copy <code>atz-dbg:…</code>
</div>
<div class="atz-dbg-toast" id="atz-dbg-toast"></div>
<script>
(function () {{
  var STORAGE = {json.dumps(storage_key)};
  var AUTO = {auto_json};
  var root = document;
  // Streamlit rerun có thể inject lại HTML — giữ 1 badge/toast mới nhất.
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
      var text = "atz-dbg:" + id;
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(text).then(function () {{ toast("Đã copy " + text); }});
      }} else {{
        toast(text);
      }}
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
