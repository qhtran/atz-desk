# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-17** — **T-150 Doing** — P0 Overview Top KL / giá phiên (human 1a).

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004) |
| Branch / HEAD | `main` @ `d794f99` — T-150 handoff (Overview Top KL P0) |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2 trừ nhu cầu mới |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace + prefs seed Done; còn mentor F1 / Auditor).
3. **P0 fix Overview:** Top KL/giá + VNINDEX lệch phiên vs Realtime/FireAnt (inbox 1530).
4. Chờ mentor F1 (T-200/T-210); P1 polish từ inbox.

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
| T-150 | P0 Overview Top KL / giá = phiên (không TC) | **Doing** | analysis, ui, datasource, tests | `analysis/volume_leaders.py`, `ui/overview_page.py`, `datasource/live_quotes.py` (reuse), `tests/test_volume_leaders.py` | Xem §6 | inbox 1530 | Xem §6 — ≤5 files; không tô màu che data |

**Quy tắc:** luôn tối đa **một** task `Doing`.

### Todo (sẵn sàng khi human chọn)

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-151 | P0 Thống nhất VNINDEX Overview ↔ Realtime | Todo | ui, ingestion/index | `overview_page`, index cards / index-feed path | Ngoài phiên Overview = Realtime = FA (~1705.91 +0.45%) hoặc caption nguồn+giờ rõ | inbox 1530 | Chỉ nguồn chỉ số; không đổi token màu. |
| T-152 | P1: lọc chỉ số khỏi Top20; POW ngoài rổ; format Trần/Sàn; label closed; PnL bar theo dấu | Todo | ui, ui_realtime | overview, board_view, sidebar_portfolio, theme | Theo đề xuất 3–4 inbox §4 | T-150 | Sau P0; có thể tách 2 PR. |
| T-153 | P1 Contrast zebra / chữ Δ trên nền tối | Todo | ui | `table_theme.py`, COLOR_TOKENS | Đọc được 1280×800 | T-150 | Theme only. |
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, … | Mentor | Mentor | **Blocked.** |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo mentor | Mentor | Mentor | **Blocked.** |
| T-220 | Brand CSS Authentik / infra soft | Blocked | infra | deploy | `user_confirmed_infra` | Human | **Blocked.** |

---

## 5. Risks & open questions

1. **P0 data Overview** — Giá Overview ≈ TC Realtime; Δ ngược (VHM/STB/MBB…) — **không** fix bằng đổi màu.
2. **Hai nguồn chỉ số** — Overview vs Realtime/index-feed.
3. **Mentor gate** F1 còn lại.
4. ~~WAIT inbox 1530~~ — **hết** (report trên `auditor/20261017-post-ux-wave-retest` @ `6932c76`).
5. ~~T-130 image drift~~ — hết.
6. Multi-agent: bus = PROGRESS only.

---

## 6. Handoff to Agent 2

**Current Doing: T-150** — P0 Overview Top KL / giá phiên (human **1a**).

### Gap (Architect pre-survey)
- `analysis/volume_leaders.volume_stats`: `Giá` = `close.iloc[-1]`, `%` = vs `close.iloc[-2]` từ OHLCV CSV.
- Auditor [live]: Overview **Giá ≈ TC Realtime** (VHM 58.90), Δ ngược FA/Realtime (61.00 +3.57%). Sidebar Redis quote **đúng** → lỗi nguồn Top KL OHLCV (bar cuối stale / thiếu phiên 16/10), không phải token màu.
- UI: `overview_page.show_volume_leaders` chỉ gọi `rank_volume_leaders()` + caption cố định — chưa ghi ngày phiên / nguồn.

### Hướng implement (ưu tiên rõ ràng)
1. **Giá + % trên bảng Top KL:** overlay từ Redis `quote:{symbol}` (reuse `datasource/live_quotes.py` / cùng đơn vị nghìn đồng như sidebar) khi có quote hợp lệ; **fallback** OHLCV.
2. **KL phiên / TB10:** giữ từ OHLCV (F1 metric); nếu bar cuối không phải phiên giao dịch gần nhất → ưu tiên bar đúng ngày phiên (detect `time` cột nếu có) — đừng bịa dữ liệu.
3. Caption: ngày phiên dùng + «Giá: Redis nếu có · KL: OHLCV».
4. (Tuỳ chọn nhỏ trong cùng PR nếu ≤5 files) loại symbol chỉ số (`VNINDEX`…) khỏi rank — nếu phình scope → để T-152.
5. Tests: unit overlay / fallback; không cần live Redis trong CI (mock).
6. `pytest tests/test_volume_leaders.py` (+ test mới) → Pass/Fail.

### Acceptance
- Cùng điều kiện ngoài phiên: VHM Overview **cùng hướng** Realtime/FA (không còn Giá=TC + Δ ngược).
- STB ~0%; MBB cùng hướng Realtime (−); caption có ngày/nguồn.
- **Không** sửa màu token để «khớp» khi data sai.

### Không đụng
- T-151 VNINDEX path; nginx/SSH; Authentik; force-push; tô màu che OHLCV
- `compose down` / volume wipe

### Commit gợi ý
`fix(overview): align Top KL price/pct with live quote session`

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
START T-150 — P0 Overview Top KL price/pct vs live session (human 1a).
Read §6. Prefer Redis quote overlay for Giá/%; OHLCV for volume metrics.
≤5 files. No color-token fake-fix. No T-151 scope creep.
pytest tests/test_volume_leaders.py Pass; update §7 + T-150 Done.
```

### Last Executor state

```
task: T-150
result: in_progress
HEAD_at_start: d794f99
notes: assigned after human 1a
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
| 2026-10-17 | executor-1 re-check inbox vẫn trống; Turns 0→1; idle |
| 2026-10-17 | **Inbox 1530 nhận** — Master summary; Todo T-150…T-153; WAIT clear |
| 2026-10-17 | **T-150 Doing** — human 1a; Redis overlay Giá/% Top KL; Master START |
