# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-17** — human **1a**: **WAIT AuditorBot inbox** (brief `1530`); Executor idle.

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004) |
| Branch / HEAD | `main` @ `2ec61de` — T-130 closed; waiting Auditor inbox `1530` |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2 trừ nhu cầu mới |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace + prefs seed Done; còn mentor F1 / Auditor).
3. **WAIT:** AuditorBot poll brief P0 `1530` → push `inbox/20261017-1530-atz-post-ux-wave-retest.md` (inbox hiện **trống**).
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
| T-140 | Auditor backlog + P0 post-UX retest brief | docs | **Master ack** — BACKLOG stale×5; brief `1530`; PROTOCOL skip; chờ inbox |
| T-130 | Deploy hygiene rebuild ALL (scope 3a) | docker | **Master ack** — image `8c872b1f46eb`; upstream PASS; stcore 200; no nginx/sshd/UFW |

### Doing

| ID | Title | Status | Modules | Target files | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|--------------|------------|------|----------------------|
| — | *(trống — WAIT AuditorBot; không giao code)* | — | — | — | — | — | — |

**Quy tắc:** luôn tối đa **một** task `Doing`.

### Todo (sẵn sàng khi human chọn)

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, `analysis/candles*`, `filter_criteria.py`, tests | Mentor chốt định nghĩa → unit test + catalog | Mentor | **Blocked.** Không đoán ngưỡng. |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo doc mentor | Spec mentor đủ → implement từng indicator 1 PR | Mentor | **Blocked.** |
| T-220 | Brand CSS Authentik / infra soft (n8n, fail2ban, cert) | Blocked | infra | deploy Authentik / VPS | Human `user_confirmed_infra: yes` trước mọi đụng auth/nginx | Human | **Blocked** trừ confirm tường minh. |

---

## 5. Risks & open questions

1. **Auditor inbox trống** (2026-10-17 check) — brief `1530` active; cần bật/poll AuditorBot.
2. **Mentor gate** cho nến mạnh–TB–yếu + BB/Ichi — không tự invent.
3. ~~T-130 image drift~~ — **hết** sau Phase B (cùng image `8c872b1f46eb`).
4. **Multi-agent:** Architect ≠ app code; Executor = 1 `Doing`; bus = PROGRESS.md only.
5. ~~HANDOFF lệch workspace~~ — hết sau T-100.
6. ~~T-110 bypass~~ — hết (regression test Pass).

---

## 6. Handoff to Agent 2

**Current Doing:** *(trống)* — human **1a** = **WAIT AuditorBot**.

### Watch criteria (Master / human)
- Kỳ vọng file: `docs/auditorbot/inbox/20261017-1530-atz-post-ux-wave-retest.md`
- Task active: `docs/auditorbot/tasks/20261017-1530-post-ux-wave-retest.md`
- Protocol: skip `stale_no_inbox` (`BACKLOG.md`)
- Prompt bot: `docs/auditorbot/PROMPT_FOR_AUDITORBOT.md`
- Khi có inbox: Master đọc → tóm tắt P0/P1 → Resolution → chuyển `reports/` nếu xử lý xong

### Executor-1
- **Idle** — không SSH, không `src/`, không tạo brief mới trừ human bảo.
- Có thể `git pull` định kỳ; nếu thấy inbox mới → báo Master (không tự Resolution lớn).

### Khi inbox về — human chọn tiếp
```
2a) Master đọc inbox + tóm tắt hành động
2b) Vẫn chờ / poll thêm
2c) Việc khác
```

### Executor notes (T-130 — archived)
- Done image `8c872b1f46eb`; Master ack `dcc465b`.

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
| executor-1 | 0 | 0 | no | idle |

### Master commands

```
WAIT_AUDITOR — human 1a
Poll/watch: docs/auditorbot/inbox/ for 20261017-1530-atz-post-ux-wave-retest.md
Executor-1: IDLE (no code, no SSH).
When inbox appears: human → 2a for Master summary.
Optional: human starts AuditorBot with PROMPT_FOR_AUDITORBOT.md
```

### Last Executor state

```
task: (none)
result: idle_wait_auditor
watch: inbox/20261017-1530-atz-post-ux-wave-retest.md
inbox_status: empty (checked 2026-10-17)
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
| 2026-10-17 | **T-140 Doing** — human 1a Auditor; Master START backlog + P0 brief |
| 2026-10-17 | **T-140 Done** — BACKLOG+brief+PROTOCOL skip stale; Status=idle; chờ commit |
| 2026-10-17 | **Master ack T-140 (human 2a)** — review OK; ship docs; chờ AuditorBot inbox |
| 2026-10-17 | **T-130 Doing HOLD SSH** — human 1a; chờ user_confirmed_infra + scope |
| 2026-10-17 | **T-130 Phase B GO** — human 3a; user_confirmed_infra: yes; scope ALL workers+UI |
| 2026-10-17 | **T-130 owner=executor-1** — human 2a; Master waits report; no Master SSH |
| 2026-10-17 | **T-130 Done** — executor-1 Phase B PASS; image 8c872b1f46eb; upstream PASS; Status=idle |
| 2026-10-17 | **Master ack T-130** — verify report; commit+push PROGRESS |
| 2026-10-17 | **WAIT_AUDITOR** — human 1a; inbox trống; brief 1530 active; Executor idle |
