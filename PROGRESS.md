# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-17** — **T-161 Phase B GO** — Exe1 deploy T-152 UI (`vnstocks` only); `user_confirmed_infra: yes`.

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004); **ADR 0006** cấm OIDC Client Streamlit |
| Branch / HEAD | `main` @ `459c446` — T-152 ship `67b26e3`; **T-161 Doing** (VPS UI `8904bb446226` → rebuild) |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2; không OIDC client trong app trừ ADR mới |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace + prefs seed Done; còn mentor F1 / Auditor).
3. ~~P0 Overview Top KL + VNINDEX~~ — T-150/T-151 + T-160 **smoke Pass**.
4. ~~T-152~~ ship; **T-161 Doing** (Exe1 deploy UI); còn T-153; mentor F1.

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
  adr/0001…0006
  bots/ (ORCHESTRATION, HANDOFF_NEXT_CHAT, vpsbot…)
  auditorbot/tasks|inbox|reports
  infrastructure/ (VPS_NETWORK, AUTHENTIK_SOCIAL_SOURCES_BRIEF), specs/
```

Target layout dài hạn (ADR 0001): `shared/` / `domain/` / `adapters/` / `services/` / `web/` — **không** big-bang; boy-scout từng PR.

---

## 3. Architecture notes

**Đã chốt (xem ADRs + HANDOFF):**
- ADR 0002: code dưới `src/atz` + PYTHONPATH.
- ADR 0003: Account UX Phase 1 headers-only (Authentik).
- ADR 0004: trading profile / vốn / risk / pin trong SQLite — **không** Authentik attributes.
- ADR 0005: bền → SQLite; nóng → Redis; test → tmp/fixtures.
- ADR 0006: **cấm** OIDC Client trong Streamlit; Social Login = Authentik Sources (brief infra).
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
- OIDC Client / JWT session trong app (ADR 0006) — trừ ADR mới + confirm chủ repo.

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
| T-150 | P0 Overview Top KL Giá/% = Redis phiên | analysis, ui, datasource, tests | **Master ack** — Redis overlay; KL OHLCV; exclude index; pytest Pass (10) |
| T-151 | P0 Overview VN indexes ↔ Realtime idx:quote | ui, datasource, tests | **Master ack** — `index_quotes` overlay sau cache; caption ts; pytest Pass (3) |
| T-160 | Deploy T-150+T-151 UI (`vnstocks` only) | docker | **Master ack** — image `8904bb446226`; upstream PASS; stcore 200; smoke checklist §6 |
| T-152 | P1 polish inbox §4 mục 3–4 | ui, ui_realtime, analysis, tests | **Master ack** — exclude/POW caption/Trần/Sàn/`closed`/PnL; `test_t152_polish` Pass (4) |

### Doing

| ID | Title | Status | Modules | Target files | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|--------------|------------|------|----------------------|
| T-161 | Deploy T-152 UI (`vnstocks` only) | **Doing** (Phase B GO) | docker | VPS `/opt/vnstocks` | pull ≥ `67b26e3`; build+up `--no-deps vnstocks`; health 200; upstream OK | `user_confirmed_infra: yes` | owner **executor-1** (Exe1) — §6 |

**Quy tắc:** luôn tối đa **một** task `Doing`.

### Todo (sẵn sàng khi human chọn)

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-153 | P1 Contrast zebra / chữ Δ trên nền tối | Todo | ui | `table_theme.py`, COLOR_TOKENS | Đọc được 1280×800 | T-150 | Theme only. |
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, … | Mentor | Mentor | **Blocked.** |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo mentor | Mentor | Mentor | **Blocked.** |
| T-220 | Brand CSS Authentik / Social Sources / infra soft | Blocked | infra | deploy + `AUTHENTIK_SOCIAL_SOURCES_BRIEF.md` | `user_confirmed_infra` | Human | **Blocked** — không Executor OIDC app. |

---

## 5. Risks & open questions

1. ~~P0 Top KL Giá≈TC~~ — **smoke Pass** — caption Redis Giá/% 11/20; MBB/CTG/GAS khớp Realtime (19.85/−0.25, 30.6/+2.68, 76.1/−0.13).
2. ~~T-151 VNINDEX Overview~~ — **smoke Pass** — VNIndex 1,705.91 (+0.45%); caption Redis index-feed 6/6 @ 16:56:54.
3. **Mentor gate** F1 còn lại.
4. ~~WAIT inbox 1530~~ — **hết** (report trên `auditor/20261017-post-ux-wave-retest` @ `6932c76`).
5. ~~T-130 image drift~~ — hết.
6. Multi-agent: bus = PROGRESS only.
7. ~~Gemini OIDC-in-Streamlit~~ — **từ chối** (ADR 0006); Social = Authentik Sources brief.

---

## 6. Handoff to Agent 2

**Current Doing: T-161** — Deploy T-152 UI. **Phase B AUTHORIZED**. Owner: **Exe1** (`executor-1`).

### Scope (LOCKED)
`user_confirmed_infra: yes` · human «để Exe1 deploy» · chỉ **`vnstocks`**  
Code ≥ `67b26e3` (T-152 trên main; docs pin `459c446`).

### Phase B — lệnh
```bash
ssh -p 22 root@112.213.88.230
cd /opt/vnstocks
git pull --ff-only origin main   # expect ≥ 67b26e3
docker compose build vnstocks
docker compose up -d --no-deps --force-recreate vnstocks
docker compose ps vnstocks
/usr/local/bin/atz-check-upstream
# curl _stcore/health → 200
```
Smoke (tuỳ): Trần/Sàn format; `closed` ngoài phiên; POW caption; PnL bar theo dấu.  
Cập nhật §7 + T-161 Done khi PASS.

### Cấm
- nginx / sshd / UFW / Authentik / `compose down` / volumes / recreate workers
- Master **không** SSH

### Master ack (T-152) — archived
- Ship `67b26e3`; `test_t152_polish` Pass (4).

### Executor notes (T-152 / T-160 / T-151 — archived)
- T-152 code Done; T-160 image `8904bb446226`; T-151 `7639ce2`.

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
user_confirmed_infra: yes
scope: vnstocks_only
owner: executor-1  (Exe1 — Master does NOT SSH)
START T-161 Phase B — SSH -p 22 → /opt/vnstocks
git pull --ff-only; docker compose build vnstocks;
up -d --no-deps --force-recreate vnstocks
atz-check-upstream + _stcore/health 200
expect code ≥ 67b26e3
NO nginx/sshd/UFW/volumes/workers.
When Done: §7 + T-161 Done; Status=idle; push PROGRESS.
```

### Last Executor state

```
task: T-161
result: authorized_awaiting_executor
HEAD_at_start: 459c446
code_min: 67b26e3
scope: vnstocks_only
user_confirmed_infra: yes
owner: executor-1
ssh: allowed :22
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
| 2026-10-17 | **T-150 Done** — Redis session overlay; pytest Pass (10); Status=idle; chờ commit |
| 2026-10-17 | **Master ack T-150 (human 2a)** — re-verify pytest Pass (10); ship code |
| 2026-10-17 | **T-151 Doing** — human 1a; overlay Overview indexes từ Redis idx:quote |
| 2026-10-17 | **T-151 Done** — index_quotes overlay; pytest Pass (3); Status=idle; chờ commit |
| 2026-10-17 | **Master ack T-151 (human 2a)** — re-verify pytest Pass (3); ship code |
| 2026-10-17 | **T-160 Doing HOLD** — human 1a deploy UI; chờ user_confirmed_infra |
| 2026-10-17 | **T-160 Phase B GO** — human 3a; user_confirmed_infra: yes; owner executor-1 |
| 2026-10-17 | **T-160 Done** — executor-1 deploy vnstocks; image 8904bb446226; upstream PASS |
| 2026-10-17 | **T-160 Done** — executor deploy; image 8904bb446226; upstream PASS; health 200 |
| 2026-10-17 | **Master ack T-160** — report OK; public→Authentik 302 (forward-auth); visual = human 1a |
| 2026-10-17 | **ADR 0006** — no OIDC client Streamlit; Social brief Authentik Sources |
| 2026-10-17 | **Ship** `@24197d0` — ADR 0006 + T-160 ack docs |
| 2026-10-17 | **T-160 visual smoke Pass** — Top KL Redis + VNINDEX 6/6 vs Realtime |
| 2026-10-17 | **T-152 Doing** — human 1a; owner executor-1; DoD inbox §4 mục 3–4 |
| 2026-10-17 | **T-152 Done** — exclude/closed/Trần/PnL; pytest Pass; Status=idle; chờ commit |
| 2026-10-17 | **Master ack T-152 (human 1a)** — re-verify test_t152_polish Pass (4); ship code |
| 2026-10-17 | **T-161 Phase B GO** — Exe1 deploy T-152 UI; user_confirmed_infra: yes; vnstocks only |
