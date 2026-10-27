/**
 * Hybrid Inspect debug overlay (pb-ui:* / atz-ui:*).
 * Priceboard: bootstrap via /api/debug-ui/config. Prod app: inject script + static/.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var STORAGE = (script && script.dataset.storageKey) || "pb-dbg-on";
  var CATALOG_URL = (script && script.dataset.catalogUrl) || "/static/ui_catalog.json";
  var REF_PREFIX = (script && script.dataset.refPrefix) || "pb-ui";
  var SURFACE = (script && script.dataset.surface) || "priceboard";

  function makeUiRef(suffix) {
    return REF_PREFIX + ":" + suffix;
  }

  var FIELD_LABELS = {
    symbol: "Mã CK",
    ceil: "Trần",
    floor: "Sàn",
    ref: "TC",
    bid1: "Mua G1",
    bid2: "Mua G2",
    bid3: "Mua G3",
    bidVol1: "KL mua 1",
    bidVol2: "KL mua 2",
    bidVol3: "KL mua 3",
    last: "Giá khớp",
    matchVol: "KL khớp",
    change: "+/-",
    ask1: "Bán G1",
    ask2: "Bán G2",
    ask3: "Bán G3",
    askVol1: "KL bán 1",
    askVol2: "KL bán 2",
    askVol3: "KL bán 3",
    vol: "Tổng KL",
    fbuy: "NN mua",
    fsell: "NN bán",
    chg: "Biến động",
    pct: "%",
    ivol: "KL rổ",
    ival: "GT rổ",
  };

  var catalog = [];
  var pinnedEl = null;
  var pinnedOutline = null;
  var rafPending = false;
  var lastHoverEl = null;

  var els = {};

  function toast(msg) {
    if (!els.toast) return;
    els.toast.textContent = msg;
    els.toast.style.display = "block";
    clearTimeout(els.toast._t);
    els.toast._t = setTimeout(function () {
      els.toast.style.display = "none";
    }, 1600);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          toast("Đã copy");
        })
        .catch(function () {
          toast(text.slice(0, 80));
        });
    } else {
      toast(text.slice(0, 120));
    }
  }

  function api() {
    return window.__pbDbg;
  }

  function syncFab() {
    if (!els.fab) return;
    var on = !!(api() && api().on);
    els.fab.setAttribute("aria-pressed", on ? "true" : "false");
    els.fab.classList.toggle("is-on", on);
    els.fab.textContent = on ? "DBG ON" : "DBG";
    els.fab.title = on
      ? "Tắt Inspect (tương đương ⌘⇧D)"
      : "Bật Inspect — tap để pin, copy ui_ref (tương đương ⌘⇧D)";
  }

  function setOn(v) {
    var a = api();
    a.on = !!v;
    try {
      sessionStorage.setItem(STORAGE, a.on ? "1" : "0");
    } catch (e) {}
    document.body.classList.toggle("pb-dbg-on", a.on);
    if (els.shield) els.shield.style.display = a.on ? "block" : "none";
    if (els.badge) els.badge.style.display = a.on ? "block" : "none";
    syncFab();
    if (!a.on) {
      hideHighlight();
      closePanel();
      unpin();
    }
  }

  function toggle() {
    setOn(!api().on);
    toast(api().on ? "Inspect ON · tap/click để pin" : "Inspect OFF");
  }

  function hashDom(el) {
    var p = domPath(el);
    var h = 0;
    for (var i = 0; i < p.length; i++) h = (h * 31 + p.charCodeAt(i)) >>> 0;
    return h.toString(36);
  }

  function domPath(el) {
    var parts = [];
    var node = el;
    while (node && node.nodeType === 1 && parts.length < 8) {
      var tag = node.tagName.toLowerCase();
      var id = node.id ? "#" + node.id : "";
      var cls =
        node.classList && node.classList.length
          ? "." + Array.prototype.slice.call(node.classList, 0, 2).join(".")
          : "";
      parts.unshift(tag + id + cls);
      node = node.parentElement;
    }
    return parts.join(" > ");
  }

  function closestWith(el, pred) {
    var n = el;
    while (n && n !== document.body) {
      if (pred(n)) return n;
      n = n.parentElement;
    }
    return null;
  }

  function resolveStTarget(anchor) {
    var box = anchor.closest('[data-testid="stElementContainer"]') || anchor.parentElement;
    if (!box) return anchor;
    var n = box.nextElementSibling;
    while (n) {
      if (n.getAttribute && n.getAttribute("data-testid") === "stElementContainer") return n;
      n = n.nextElementSibling;
    }
    return box;
  }

  function findStreamlitAnchor(el) {
    var container = closestWith(el, function (n) {
      return n.getAttribute && n.getAttribute("data-testid") === "stElementContainer";
    });
    if (!container) return null;
    var prev = container.previousElementSibling;
    while (prev) {
      if (prev.getAttribute && prev.getAttribute("data-atz-dbg")) return prev;
      if (prev.querySelector) {
        var nested = prev.querySelector("[data-atz-dbg]");
        if (nested) return nested;
      }
      prev = prev.previousElementSibling;
    }
    return null;
  }

  function resolveStreamlit(el) {
    var anchor = closestWith(el, function (n) {
      return n.getAttribute && n.getAttribute("data-atz-dbg");
    });
    if (!anchor) anchor = findStreamlitAnchor(el);
    if (anchor) {
      var dbgId = anchor.getAttribute("data-atz-dbg");
      var target = resolveStTarget(anchor);
      return {
        ui_ref: makeUiRef(dbgId),
        element: target,
        breadcrumb: ["atz.vn", dbgId],
        tick_field: null,
        symbol: null,
        domPath: domPath(target),
      };
    }
    if (el.closest('[data-testid="stSidebar"]')) {
      return {
        ui_ref: makeUiRef("DBG-SIDEBAR"),
        element: el.closest('[data-testid="stSidebar"]'),
        breadcrumb: ["atz.vn", "Sidebar"],
        tick_field: null,
        symbol: null,
        domPath: domPath(el),
      };
    }
    if (el.closest('[data-testid="stMain"]')) {
      return {
        ui_ref: makeUiRef("DBG-MAIN"),
        element: el.closest('[data-testid="stMain"]'),
        breadcrumb: ["atz.vn", "Main"],
        tick_field: null,
        symbol: null,
        domPath: domPath(el),
      };
    }
    var nav = el.closest('[data-testid="stButtonGroup"]');
    if (nav) {
      return {
        ui_ref: makeUiRef("DBG-NAV"),
        element: nav,
        breadcrumb: ["atz.vn", "Nav"],
        tick_field: null,
        symbol: null,
        domPath: domPath(nav),
      };
    }
    return null;
  }

  function resolveFromElement(el) {
    if (!el || el === document.body) return null;

    if (SURFACE === "atz") {
      var st = resolveStreamlit(el);
      if (st) return st;
    }

    if (SURFACE !== "priceboard") {
      var atdOnly = closestWith(el, function (n) {
        return n.getAttribute && n.getAttribute("data-atd-id");
      });
      if (atdOnly) {
        var aid = atdOnly.getAttribute("data-atd-id");
        return {
          ui_ref: aid,
          element: atdOnly,
          breadcrumb: breadcrumbFromRef(aid),
          tick_field: null,
          symbol: null,
          domPath: domPath(atdOnly),
        };
      }
      return {
        ui_ref: makeUiRef("pick." + hashDom(el)),
        element: el,
        breadcrumb: ["Pick", el.tagName.toLowerCase()],
        tick_field: null,
        symbol: null,
        domPath: domPath(el),
      };
    }

    var td = closestWith(el, function (n) {
      return n.tagName === "TD" && n.getAttribute("data-f");
    });
    if (td) {
      var tr = closestWith(td, function (n) {
        return n.tagName === "TR" && (n.dataset.symbol || n.id);
      });
      var sym =
        (tr && (tr.dataset.symbol || (tr.id || "").replace(/^row-/, ""))) || "";
      var field = td.getAttribute("data-f") || "";
      var tableKind = tr && tr.closest("#signals-table")
        ? "signals"
        : tr && tr.closest("#portfolio-table")
          ? "portfolio"
          : "equity";
      var refStr;
      if (tableKind === "signals") {
        refStr = makeUiRef("signals.row." + sym + ".cell." + field);
      } else if (tableKind === "portfolio") {
        refStr = makeUiRef("portfolio.row." + sym + ".cell." + field);
      } else {
        refStr = makeUiRef("iboard.equity.row." + sym + ".cell." + field);
      }
      return {
        ui_ref: refStr,
        element: td,
        breadcrumb: buildTableBreadcrumb(tableKind, sym, field),
        tick_field: field,
        symbol: sym || null,
        domPath: domPath(td),
      };
    }

    var idxCard = closestWith(el, function (n) {
      return n.classList && n.classList.contains("idx-card");
    });
    if (idxCard) {
      var idxSym = idxCard.getAttribute("data-idx") || "";
      var inner = closestWith(el, function (n) {
        return n.getAttribute && n.getAttribute("data-f");
      });
      if (inner && inner !== idxCard) {
        var f = inner.getAttribute("data-f");
        return {
          ui_ref: makeUiRef("iboard.index." + idxSym + "." + f),
          element: inner,
          breadcrumb: ["iBoard", "Chỉ số " + idxSym, FIELD_LABELS[f] || f],
          tick_field: f,
          symbol: idxSym,
          domPath: domPath(inner),
        };
      }
      if (el.tagName === "svg" || closestWith(el, function (n) {
        return n.tagName === "svg" && n.classList.contains("spark");
      })) {
        return {
          ui_ref: makeUiRef("iboard.index." + idxSym + ".spark"),
          element: idxCard,
          breadcrumb: ["iBoard", "Chỉ số " + idxSym, "Spark chart"],
          tick_field: "spark",
          symbol: idxSym,
          domPath: domPath(idxCard),
        };
      }
      return {
        ui_ref: makeUiRef("iboard.index." + idxSym),
        element: idxCard,
        breadcrumb: ["iBoard", "Chỉ số " + idxSym],
        tick_field: null,
        symbol: idxSym,
        domPath: domPath(idxCard),
      };
    }

    var atd = closestWith(el, function (n) {
      return n.getAttribute && n.getAttribute("data-atd-id");
    });
    if (atd) {
      var id = atd.getAttribute("data-atd-id");
      return {
        ui_ref: id,
        element: atd,
        breadcrumb: breadcrumbFromRef(id),
        tick_field: null,
        symbol: null,
        domPath: domPath(atd),
      };
    }

    return {
      ui_ref: makeUiRef("pick." + hashDom(el)),
      element: el,
      breadcrumb: ["Pick", el.tagName.toLowerCase()],
      tick_field: null,
      symbol: null,
      domPath: domPath(el),
    };
  }

  function breadcrumbFromRef(ref) {
    var parts = ref.replace(new RegExp("^" + REF_PREFIX + ":"), "").split(".");
    if (REF_PREFIX === "atz-ui" && parts[0]) {
      return ["atz.vn"].concat(parts);
    }
    var labels = [];
    if (parts[0] === "app") {
      labels.push("App");
      if (parts[1] === "tab") labels.push("Tab " + (parts[2] || ""));
      else if (parts[1] === "conn") labels.push("WebSocket");
      else if (parts[1] === "settings") labels.push("Cài đặt");
      else labels.push(parts.slice(1).join(" · "));
    } else if (parts[0] === "iboard") {
      labels.push("iBoard");
      if (parts[1] === "market") labels.push("Rổ " + (parts[2] || ""));
      else if (parts[1] === "search") labels.push("Tìm mã");
      else if (parts[1] === "index-bar") labels.push("Thanh chỉ số");
      else labels.push(parts.slice(1).join(" · "));
    } else if (parts[0] === "signals") labels.push("Bộ lọc tín hiệu");
    else if (parts[0] === "portfolio") labels.push("Danh mục");
    else if (parts[0] === "news") labels.push("Tin tức");
    else labels.push(parts.join(" · "));
    return labels;
  }

  function buildTableBreadcrumb(kind, sym, field) {
    var base =
      kind === "signals"
        ? "Bộ lọc tín hiệu"
        : kind === "portfolio"
          ? "Danh mục"
          : "Bảng cổ phiếu";
    return ["iBoard", base, sym || "—", FIELD_LABELS[field] || field];
  }

  function catalogMatch(uiRef) {
    for (var i = 0; i < catalog.length; i++) {
      var e = catalog[i];
      if (e.matchType === "prefix" && uiRef.indexOf(e.match) === 0) return e;
      if (e.matchType !== "prefix" && uiRef === e.match) return e;
    }
    return null;
  }

  function buildDebugCard(resolved) {
    var cat = catalogMatch(resolved.ui_ref);
    var card = {
      ui_ref: resolved.ui_ref,
      breadcrumb: (cat && cat.breadcrumb) || resolved.breadcrumb,
      tick_field: resolved.tick_field,
      symbol: resolved.symbol,
      dom: {
        tag: resolved.element.tagName.toLowerCase(),
        path: resolved.domPath,
      },
      hints: (cat && cat.hints) || {},
      err_codes: (cat && cat.err_codes) || [],
    };
    if (cat && cat.breadcrumb && resolved.symbol) {
      card.breadcrumb = cat.breadcrumb.concat([
        resolved.symbol,
        FIELD_LABELS[resolved.tick_field] || resolved.tick_field || "",
      ]).filter(Boolean);
    }
    return card;
  }

  function positionHighlight(el) {
    if (!els.highlight || !els.hoverLabel || !el) return;
    var r = el.getBoundingClientRect();
    els.highlight.style.display = "block";
    els.highlight.style.left = r.left + "px";
    els.highlight.style.top = r.top + "px";
    els.highlight.style.width = r.width + "px";
    els.highlight.style.height = r.height + "px";
    var res = resolveFromElement(el);
    els.hoverLabel.textContent = res ? res.ui_ref : "";
    els.hoverLabel.style.display = res ? "block" : "none";
    els.hoverLabel.style.left = Math.max(4, r.left) + "px";
    els.hoverLabel.style.top = Math.max(4, r.top - 22) + "px";
  }

  function hideHighlight() {
    if (els.highlight) els.highlight.style.display = "none";
    if (els.hoverLabel) els.hoverLabel.style.display = "none";
  }

  function onShieldMove(ev) {
    if (!api().on) return;
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(function () {
      rafPending = false;
      els.shield.style.pointerEvents = "none";
      var el = document.elementFromPoint(ev.clientX, ev.clientY);
      els.shield.style.pointerEvents = "auto";
      if (!el || el.closest(".pb-dbg-panel") || el.closest(".pb-dbg-badge")) {
        hideHighlight();
        lastHoverEl = null;
        return;
      }
      lastHoverEl = el;
      positionHighlight(el);
    });
  }

  function unpin() {
    if (pinnedEl) pinnedEl.classList.remove("pb-dbg-pinned-outline");
    pinnedEl = null;
  }

  function pinElement(el) {
    unpin();
    pinnedEl = el;
    if (pinnedEl) pinnedEl.classList.add("pb-dbg-pinned-outline");
  }

  function openPanel(card) {
    if (!els.panel) return;
    els.panel.classList.add("is-open");
    els.panelRef.textContent = card.ui_ref;
    els.panelCrumb.textContent = card.breadcrumb.join(" › ");
    els.panelPre.textContent = JSON.stringify(card, null, 2);
    els.panel.dataset.card = JSON.stringify(card);
    var spec = (card.hints && card.hints.spec) || "";
    els.panelSpec.href = spec ? "/" + spec.replace(/^\//, "") : "#";
    els.panelSpec.style.display = spec ? "inline-block" : "none";
  }

  function closePanel() {
    if (els.panel) els.panel.classList.remove("is-open");
    unpin();
  }

  function onShieldClick(ev) {
    if (!api().on) return;
    ev.preventDefault();
    ev.stopPropagation();
    var el = lastHoverEl || document.elementFromPoint(ev.clientX, ev.clientY);
    if (!el) return;
    var resolved = resolveFromElement(el);
    if (!resolved) return;
    pinElement(resolved.element);
    openPanel(buildDebugCard(resolved));
  }

  function mountUi() {
    els.fab = document.createElement("button");
    els.fab.type = "button";
    els.fab.id = "pb-dbg-fab";
    els.fab.className = "pb-dbg-fab";
    els.fab.setAttribute("aria-label", "Toggle Inspect debug");
    els.fab.setAttribute("data-atd-id", "pb-ui:debug.fab");
    els.fab.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      toggle();
    });

    els.badge = document.createElement("div");
    els.badge.className = "pb-dbg-badge";
    els.badge.innerHTML =
      "Inspect ON · ⌘⇧D / nút DBG · Esc tắt<br/>Tap/click pin · Copy JSON / ui_ref";

    els.toast = document.createElement("div");
    els.toast.className = "pb-dbg-toast";

    els.shield = document.createElement("div");
    els.shield.className = "pb-dbg-shield";
    els.shield.style.display = "none";
    els.shield.addEventListener("mousemove", onShieldMove, true);
    els.shield.addEventListener(
      "touchmove",
      function (ev) {
        if (!api().on || !ev.touches || !ev.touches[0]) return;
        onShieldMove({
          clientX: ev.touches[0].clientX,
          clientY: ev.touches[0].clientY,
        });
      },
      true
    );
    els.shield.addEventListener("click", onShieldClick, true);

    els.highlight = document.createElement("div");
    els.highlight.className = "pb-dbg-highlight";
    els.highlight.style.display = "none";

    els.hoverLabel = document.createElement("div");
    els.hoverLabel.className = "pb-dbg-hover-label";
    els.hoverLabel.style.display = "none";

    els.panel = document.createElement("aside");
    els.panel.className = "pb-dbg-panel";
    els.panel.innerHTML =
      '<div class="pb-dbg-panel-head"><span>Debug card</span>' +
      '<button type="button" id="pb-dbg-close">✕</button></div>' +
      '<div class="pb-dbg-panel-body">' +
      '<div class="pb-dbg-crumb" id="pb-dbg-crumb"></div>' +
      '<div id="pb-dbg-ref" style="font-family:monospace;font-size:11px;word-break:break-all"></div>' +
      '<div class="pb-dbg-actions">' +
      '<button type="button" class="primary" id="pb-dbg-copy-json">Copy JSON</button>' +
      '<button type="button" id="pb-dbg-copy-ref">Copy ui_ref</button>' +
      '<a id="pb-dbg-spec" href="#" target="_blank" rel="noopener" style="font-size:11px;color:#93c5fd">Spec</a>' +
      "</div>" +
      '<pre id="pb-dbg-pre"></pre></div>';

    document.body.appendChild(els.shield);
    document.body.appendChild(els.highlight);
    document.body.appendChild(els.hoverLabel);
    document.body.appendChild(els.badge);
    document.body.appendChild(els.fab);
    document.body.appendChild(els.toast);
    document.body.appendChild(els.panel);

    els.panelRef = document.getElementById("pb-dbg-ref");
    els.panelCrumb = document.getElementById("pb-dbg-crumb");
    els.panelPre = document.getElementById("pb-dbg-pre");
    els.panelSpec = document.getElementById("pb-dbg-spec");

    document.getElementById("pb-dbg-close").addEventListener("click", closePanel);
    document.getElementById("pb-dbg-copy-json").addEventListener("click", function () {
      var raw = els.panel.dataset.card;
      if (raw) copyText(raw);
    });
    document.getElementById("pb-dbg-copy-ref").addEventListener("click", function () {
      if (els.panelRef) copyText(els.panelRef.textContent || "");
    });
    syncFab();
  }

  function onKey(ev) {
    var key = (ev.key || "").toLowerCase();
    if (key === "escape") {
      if (els.panel && els.panel.classList.contains("is-open")) {
        closePanel();
        ev.preventDefault();
        return;
      }
      if (api().on) {
        setOn(false);
        toast("Inspect OFF");
        ev.preventDefault();
      }
      return;
    }
    if (key === "d" && ev.shiftKey && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      toggle();
    }
  }

  function applyFocusQuery() {
    var code = new URLSearchParams(location.search).get("focus");
    if (!code || !/^ERR-PB-\d{3}$/.test(code)) return;
    for (var i = 0; i < catalog.length; i++) {
      var e = catalog[i];
      if ((e.err_codes || []).indexOf(code) >= 0 && e.match) {
        toast("focus " + code + " → " + e.match);
        break;
      }
    }
  }

  function loadCatalog() {
    return fetch(CATALOG_URL)
      .then(function (r) {
        return r.ok ? r.json() : { entries: [] };
      })
      .then(function (doc) {
        catalog = (doc && doc.entries) || [];
      })
      .catch(function () {
        catalog = [];
      });
  }

  function init() {
    mountUi();
    window.__pbDbg = {
      on: false,
      toggle: toggle,
      setOn: setOn,
      resolve: resolveFromElement,
      buildCard: function (el) {
        return buildDebugCard(resolveFromElement(el));
      },
    };
    try {
      api().on = sessionStorage.getItem(STORAGE) === "1";
    } catch (e) {
      api().on = false;
    }
    document.body.classList.toggle("pb-dbg-on", api().on);
    els.shield.style.display = api().on ? "block" : "none";
    els.badge.style.display = api().on ? "block" : "none";
    syncFab();

    if (!window.__pbDbgKeyBound) {
      window.addEventListener("keydown", onKey, true);
      window.__pbDbgKeyBound = true;
    }

    loadCatalog().then(function () {
      applyFocusQuery();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
