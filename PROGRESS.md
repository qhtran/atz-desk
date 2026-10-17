# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-17** — **T-120 Doing** — giao executor-1 wire prefs SQLite.

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004) |
| Branch / HEAD | `main` @ `9a528ce` — Master ack T-110; tiếp T-120 |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2 trừ nhu cầu mới |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace đã ship; còn wire prefs + mentor F1 còn lại).
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

### Doing

| ID | Title | Status | Modules | Target files | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|--------------|------------|------|----------------------|
| T-120 | Wire prefs workspace → Bộ lọc / sidebar (SQLite nhất quán) | **Doing** | ui, datasource, tests | `datasource/user_trading.py`, `ui/filters_page.py`, `ui/pages.py`, `ui/trading_workspace_page.py` (nếu cần), `tests/test_user_trading.py` | Xem §6 | T-040 | Xem §6 Handoff — **≤5 files**; không schema mới; không ghi DB mỗi tick |

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

**Current Doing: T-120** — Wire prefs workspace → Bộ lọc / sidebar (SQLite nhất quán).

### Gap (Architect pre-survey — không implement)
- Sidebar (`pages.render_sidebar`): hydrate ROE/KL/RS/`top_n` từ `load_filter_defaults` **một lần** vào `session_state` — OK tạm.
- Workspace Lưu đã ghi SQLite + sync `sidebar_*` keys — OK.
- **Lỗ hổng:** `filters_page.show_filters` seed param từ `saved.parameters` hoặc `ParamSpec.default` (registry/`config`) — **không** đọc `trading_profile.filter_defaults` (RSI/MACD đã lưu ở workspace).
- Risk sidebar đã đọc SQLite qua `sidebar_portfolio` — không bắt buộc đụng trừ khi lệch.

### Làm gì (executor-1)
1. `git pull --ff-only origin main` (kỳ vọng ≥ `9a528ce`).
2. Thêm helper **pure** trong `datasource/user_trading.py` (vd. `filter_defaults_param_overlay(prefs) -> dict`) map các key trùng tên param filter: `rsi_oversold`, `rsi_overbought`, `macd_fast`, `macd_slow`, `macd_signal` (+ alias nếu registry dùng tên khác — kiểm `filters/*.py` ParamSpec).
3. Trong `ui/filters_page.py`: khi build `current` cho mỗi filter, merge:
   `overlay = filter_defaults_param_overlay(load_filter_defaults(user))`
   → `current = {**overlay, **(saved.parameters or {})}`  
   (**saved thắng** nếu user đã Lưu cấu hình filter).
4. Sidebar: giữ hydrate-from-SQLite; sau Lưu workspace đã sync — nếu thiếu sync `sidebar_top_n`/risk thì bổ sung tối thiểu. **Không** `persist_*` khi đổi widget sidebar / realtime tick.
5. Test: unit cho overlay + 1 case merge saved-wins; chạy `PYTHONPATH=src/atz pytest tests/test_user_trading.py -q` (+ test mới nếu tách file). Báo **Pass/Fail**.
6. Cập nhật PROGRESS: T-120 → Done; Last Executor state; Turns++; Files this task; Signals nếu cần fork.

### Không đụng
- Schema SQLite mới; Authentik; ingestion/filter_runner/alert/position; nginx/SSH
- Đổi semantics filter F1 / registry labels
- Ghi DB mỗi lần sidebar đổi số
- Force-push; >5 files → ghi `SIGNAL_NEED_FORK` trước khi phình scope

### Commit (khi human bảo hoặc Pass + human 2a-style)
- Gợi ý: `feat(ui): seed filter params from trading_profile defaults`

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
| executor-1 | 0 | 0 | no | active |

### Master commands

```
START T-120 — Wire prefs SQLite → filters_page + sidebar consistency.
Read §6 Handoff. Stay ≤5 files. Update this §7 Turns/Files/Signals each turn.
When Done: pytest Pass/Fail + Last Executor state + set Status=idle; clear Doing.
```

### Last Executor state

```
task: T-120
result: in_progress
commit: (pending)
pytest: (pending)
files: (pending)
notes: assigned by Master after human chose 1a
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
