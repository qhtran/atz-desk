# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-17** — Master ack **T-120 Done** (human 2a); pytest Pass (7).

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004) |
| Branch / HEAD | `main` @ `d19ef30` — T-120 seed filter params + Master ack |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2 trừ nhu cầu mới |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace + prefs seed Done; còn mentor F1 / Auditor).
3. Auditor queue / survey baseline còn trống inbox.
4. Chờ mentor cho nến mạnh–TB–yếu, Bollinger, Ichimoku, phần II.

---

## 2. Folder map (current)

```text
src/atz/
  app.py, config.py, dashboard.py, khuyen_nghi.py
  ui/                 # Streamlit pages (realtime, account, workspace, desk, filters…)
  ui_realtime/        # board_view, data, index_cards, config
  datasource/         # quotes, user_trading, capital, frames…
  ingestion/          # KBS/VCI → Redis
  filter_runner/      # stream → signals
  alert_dispatcher/   # Telegram / email / in-app
  position_monitor/   # P&L + SL/TP alerts
  filters/, analysis/, engine/, storage/, order_helper/
config/*.yaml         # ingestion, filter_runner, alert, position, ui_realtime, debug_overlay…
tests/test_*.py       # map theo module
docs/
  architecture.md, troubleshooting.md, COLOR_TOKENS.md, F1_CHECKLIST_UI.md
  adr/0001…0005
  bots/ (ORCHESTRATION, HANDOFF_NEXT_CHAT, vpsbot…)
  auditorbot/tasks|inbox|reports
  infrastructure/, specs/
```

Target layout dài hạn (ADR 0001): `shared/` / `domain/` / `adapters/` / `services/` / `web/` — **không** big-bang; boy-scout từng PR.

---

## 3. Architecture notes

**Đã chốt (xem ADRs + HANDOFF):**
- ADR 0002: code dưới `src/atz` + PYTHONPATH.
- ADR 0003: Account UX Phase 1 headers-only (Authentik).
- ADR 0004: trading profile / vốn / risk / pin trong SQLite — **không** Authentik attributes.
- ADR 0005: bền → SQLite; nóng → Redis; test → tmp/fixtures.
- UI bảng: mọi bảng qua `render_data_table(variant=…)` (`docs/COLOR_TOKENS.md`).
- Debug overlay: `config/debug_overlay.yaml` / `ATZ_DEBUG_OVERLAY`.
- SSH ops: ưu tiên host `:22`; **cấm** đụng nginx stream / sshd / UFW trừ human confirm.
- Bot code paused; AuditorBot giữ survey UI; Cursor = code/deploy.
- **Architect không viết app code**; Executor chỉ 1 task `Doing`; giao tiếp tab qua PROGRESS.md.

**Đã ship gần đây (không mở lại trừ bug):**
- Pin + live pinned strip; flash tick; OAH copy string; vốn/risk per-user.
- Trading workspace tab + filter prefs SQLite — **Done**.
- Unify tables → 3 variants (`cf68947`) — **Done**.
- F1 filter mode nến/RSI/MACD (catalog + logic hàng 1–3).
- T-110 regression: sole `st.dataframe` entry = `ui/components.py` — **Done** trên `main` (`8e98e0f`).

**NON-goals:**
- Greenfield rewrite / SPA.
- Auto-order / broker API trading.
- Seed test vào DB production.
- Force-push; commit secrets.

---

## 4. Task board

Status ∈ `Todo` | `Doing` | `Done` | `Blocked`.

### Done (gần đây — neo kiến trúc)

| ID | Title | Modules | Notes |
|----|-------|---------|-------|
| T-010 | Per-user capital + risk SQLite | datasource, storage | ADR 0004/0005 |
| T-020 | Pin symbols + realtime board | ui, ui_realtime, datasource | pin strip `1a1dde5` |
| T-030 | OAH standard copy string | order_helper | `604b51b` |
| T-040 | Trading workspace + filter prefs + Ghim glance | ui, datasource | `c71dc2c` |
| T-050 | Debug overlay + table COL/ROW chips | ui | kill-switch YAML |
| T-060 | Unify `render_data_table` 3 variants | ui | `cf68947` |
| T-100 | Đồng bộ docs handoff với HEAD thực tế | docs | HANDOFF + PROGRESS khớp Done |
| T-110 | Verify không còn bảng bypass theme | ui, tests | **Agent2 Done** — grep sạch; regression Pass (7); ship `8e98e0f` |
| T-120 | Wire prefs → Bộ lọc (SQLite seed RSI/MACD) | ui, datasource, tests | **Master ack** — overlay+seed; saved thắng; MA≠MACD; pytest Pass (7) |

### Doing

| ID | Title | Status | Modules | Target files | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|--------------|------------|------|----------------------|
| — | *(trống — chờ human chọn Todo)* | — | — | — | — | — | — |

**Quy tắc:** luôn tối đa **một** task `Doing`.

### Todo (sẵn sàng khi human chọn)

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-130 | Deploy hygiene: rebuild services lệch image | Todo | docker | Compose tại VPS `/opt/vnstocks` (không sửa nginx) | Services ingestion/index/alert/position chạy image mới nếu human xác nhận lệch; `atz-check-upstream` OK nếu có | Human confirm SSH | **Chỉ** `docker compose build/up --no-deps <svc>` qua `:22`. Không đụng stream/sshd/UFW. Không force-push. |
| T-140 | Auditor: thu hoạch / đóng task cũ hoặc brief retest mới | Todo | docs | `docs/auditorbot/tasks/*`, `inbox/`, `reports/` | Inbox trống đã xử lý (archive hoặc brief mới); 1 task P0 rõ ràng nếu cần survey | — | Docs only trong `docs/auditorbot/`. Không code app. |
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, `analysis/candles*`, `filter_criteria.py`, tests | Mentor chốt định nghĩa → unit test + catalog | Mentor | **Blocked.** Không đoán ngưỡng. |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo doc mentor | Spec mentor đủ → implement từng indicator 1 PR | Mentor | **Blocked.** |
| T-220 | Brand CSS Authentik / infra soft (n8n, fail2ban, cert) | Blocked | infra | deploy Authentik / VPS | Human `user_confirmed_infra: yes` trước mọi đụng auth/nginx | Human | **Blocked** trừ confirm tường minh. |

---

## 5. Risks & open questions

1. **Auditor inbox trống** dù nhiều task trong `tasks/` — survey có thể stalled.
2. **Mentor gate** cho nến mạnh–TB–yếu + BB/Ichi — không tự invent.
3. **Image drift** trên VPS — cần human xác nhận trước T-130.
4. **Multi-agent:** Architect ≠ app code; Executor = 1 `Doing`; bus = PROGRESS.md only.
5. ~~HANDOFF lệch workspace~~ — hết sau T-100.
6. ~~T-110 bypass~~ — hết (regression test Pass).

---

## 6. Handoff to Agent 2

**Current Doing:** *(trống)* — chờ human chọn Todo.

```
1a) T-140 — Auditor tasks / inbox
1b) T-130 — Deploy hygiene (cần confirm SSH)
1c) Chờ — không giao Executor
```

### Executor notes (T-120 — Done, Master ack 2a)
- `filter_defaults_param_overlay` + `seed_filter_parameters` trong `user_trading.py`
  (ParamSpec: `oversold`/`overbought`/`fast`/`slow`/`signal`; MA không seed MACD).
- `filters_page.show_filters`: seed từ SQLite; **saved.parameters thắng**.
- Sidebar: giữ hydrate một lần — không đổi.
- Master re-verify: `PYTHONPATH=src/atz .venv/bin/python -m pytest tests/test_user_trading.py -q` → **7 passed**.

### Executor notes (T-110 — archived)
- Done @ `8e98e0f`; Master ack `9a528ce`.

---

## 7. Agent sessions / fork

Bus duy nhất giữa tab = file này. Architect commit+push PROGRESS mỗi khi đổi Handoff / fork / bảng sessions.

### Auto-fork rules (mọi tab đọc mỗi turn)

Fork khi **bất kỳ** điều kiện đúng:
- Task `Doing` cần **>5 files** HOẶC tạo **module/package mới**
- Code Agent turns trong tab hiện tại **≥15** (warn) / **≥20** (hard fork)
- Code Agent ghi signal: `SIGNAL_NEED_FORK` / `SIGNAL_CONTEXT_HEAVY` / `slowing=yes`
- Human báo Executor tab đang lag

Khi fork, ghi banner vào **Master commands** (hoặc ngay dưới bảng):

```text
🚨 [ACTION REQUIRED]: CONTEXT EXCEEDED. Please open a NEW COMPOSER TAB,
load @PROGRESS.md, and continue with Task <TASK-ID>.
Reason: <…>
```

Sau đó: session cũ `Status=paused_fork`; **giữ đúng một** task `Doing`.

| Tab | Turns | Files this task | Slowing? | Status |
|-----|------:|----------------:|----------|--------|
| executor-1 | 1 | 0 | no | idle |

### Master commands

(none) — chờ human chọn Todo tiếp

### Last Executor state

```
task: T-120
result: Done
HEAD_at_start: 93988e7
commit: d19ef30
pytest: Pass (7) tests/test_user_trading.py — Master re-verify OK
files:
  - src/atz/datasource/user_trading.py
  - src/atz/ui/filters_page.py
  - tests/test_user_trading.py
  - PROGRESS.md
master_ack: human 2a
paused_fork: no
```

### Signals

(none)

---

## Changelog (PROGRESS)

| Khi | Thay đổi |
|-----|----------|
| 2026-10-17 | Tạo file; snapshot HEAD `cf68947`; T-010…T-060 Done; Todo T-100…T-140; Blocked T-200…T-220 |
| 2026-10-17 | **T-100 Done** — sync HANDOFF + PROGRESS; Trading workspace / pin strip / 3 variants = Done |
| 2026-10-17 | **T-110 Doing** — handoff Agent 2 (audit + regression test; pre-survey sạch) |
| 2026-10-17 | **T-110 Done** — bypass = 0; regression test Pass (7); Handoff clear |
| 2026-10-17 | **§7 Agent sessions / fork** — Auto Fork via PROGRESS only; sessions table |
| 2026-10-17 | **§7 chuẩn hóa** — bảng `executor-1` + Master commands / Last Executor state / Signals |
| 2026-10-17 | executor-1 Turns 0→1 (Auto Fork ack) |
| 2026-10-17 | **Master ack Agent2 xong T-110** — Last Executor state ghi Done; Status=idle |
| 2026-10-17 | **T-120 Doing** — human 1a; Master commands START; executor-1 active Turns=0 |
| 2026-10-17 | **T-120 Done** — overlay+seed RSI/MACD; pytest Pass (7); Status=idle; chờ commit |
| 2026-10-17 | **Master ack T-120 (human 2a)** — re-verify pytest Pass; ship code + PROGRESS |
