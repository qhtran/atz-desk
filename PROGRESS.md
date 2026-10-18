# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Bus duy nhất giữa tab: **file này** (không dùng bus file khác).
> Cập nhật: **2026-10-18** — **T-232 Done** — VPS `main` @ `c5d1e6c`; image `2900f583873a`.

### Naming convention (bắt buộc)

| Alias | Cũng gọi là | Vai trò | Làm / không làm |
|-------|-------------|---------|-----------------|
| **ag1** | agent1, **Master** | Architect / orchestrator | Plan, authorize, ack, brief giao việc — **không code**, không SSH, không smoke dài |
| **ag2** | agent2, **Exe1**, executor-1 | Code Executor | Code app (`src/atz`), test, deploy khi được authorize — đúng task `Doing` |
| **ag3** | agent3, **Support**, **sp1** | Support | Việc phụ: `scripts/tools/*`, doc2md, reverse-engineer mentor, seed/spec — **không** production app/deploy trừ Master giao rõ |

Exe2 = executor-2 (standby khi fork) — vẫn dưới nhánh **ag2**, không đổi alias.

### Bus protocol — ít copy-paste (bắt buộc từ 2026-10-18)

**Human ↔ ag1:** chỉ trả lời **số** (`1a`, `2b`…). Không paste brief dài.

**ag1:** ghi START/ack/`Master commands` vào **PROGRESS.md** → `commit+push` bus (và code khi human bảo). Không nhờ human chuyển tin.

**ag2 / ag3 (mỗi turn):**
1. `git pull --ff-only`
2. Đọc `Master commands` + §6 / §6b Doing
3. Nếu `Doing` đúng role mình → làm đến Done → cập nhật Last * state trên PROGRESS → `commit+push` (code + bus)
4. Báo human **một dòng** (tuỳ chọn): `T-230 Done · master_ack pending` — hoặc im lặng; human chỉ nói với ag1: `ack` / `1a`

**Cấm:** paste §START dài giữa tab; human làm “bưu tá” brief.

**Hook ngắn (tab ag2/ag3):** mở chat với `@PROGRESS.md` + câu cố định: `Pull bus. Làm task Doing của mình nếu có. Xong cập nhật PROGRESS + push.`

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004); **ADR 0006** cấm OIDC Client Streamlit |
| Branch / HEAD | **`main` @ `c5d1e6c`+** — VPS UI `2900f583873a` (T-232) |
| NON-goal | Không đặt lệnh tự động; không SPA/BFF Phase 2; không OIDC client trong app trừ ADR mới |
| `user_confirmed_infra` | **yes** — T-232 Done; VPS on `main`; `vnstocks` only |

**Active goals (ưu tiên sản phẩm):**
1. Giữ pipeline near-realtime ổn định + UI bảng thống nhất (`realtime` / `analytical` / `compact`).
2. Hoàn thiện UX trading cá nhân (workspace + prefs seed Done; còn mentor F1 / Auditor).
3. ~~P0 Overview Top KL + VNINDEX~~ — T-150/T-151 + T-160 **smoke Pass**.
4. ~~T-152…T-163~~; mentor F1; **T-220/T-221 SSO + approve**.

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
  adr/0001…0007
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
- ADR 0007: Exe1 deploy gate — `user_confirmed_infra: yes`; Master không SSH.
- UI bảng: mọi bảng qua `render_data_table(variant=…)` (`docs/COLOR_TOKENS.md`).
- Debug overlay: `config/debug_overlay.yaml` / `ATZ_DEBUG_OVERLAY`.
- SSH ops: ưu tiên host `:22`; **cấm** đụng nginx stream / sshd / UFW trừ human confirm.
- Bot code paused; AuditorBot giữ survey UI; Cursor = code/deploy.
- **ag1 (Master)** = plan / authorize / ack only — không tự code, không tự smoke/deploy/SSH. **ag2 (Exe1)** execute. **ag3 (sp1)** = việc phụ / tools / mentor analysis. Context đầy / fork → mở **Exe2** (vẫn ag2, tab mới + PROGRESS).

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
| T-161 | Deploy T-152 UI (`vnstocks` only) | docker | **Master ack** — image `8b8bba1590af`; upstream PASS; stcore 200; public→Authentik 302 |
| T-153 | P1 Contrast zebra / chữ Δ trên nền tối | ui, tests | **Master ack** — ZEBRA_ODD; skip signed; font-weight 700; pytest Pass (9) |
| T-162 | Deploy T-153 UI (`vnstocks` only) | docker | **Master ack** — image `4aaa437be56c`; pull `9e6aef3`; upstream PASS; health 200; public→302 |
| T-163 | Smoke contrast T-153 trên atz.vn | ui | **Master ack** — Overview TopKL + Realtime + idx + sidebar PnL readable @ 1280×800 |
| T-220 | Authentik SSO Sources + enrollment pending approve | infra | **Done** — enrollment + Sources; secrets synced; outbox `1830-DONE` |
| T-221 | Smoke SSO live Google/FB | infra | **Master ack Pass** — Google login OK; đổi MK OK; connection `mydev`; C Skip; outbox `2320`+ack |
| T-230 | F3 cột Cảnh báo UI + alert engine | analysis, ui, tests | **Master ack Pass** — f3_alerts + Watchlist F3; pytest Pass (7); no deploy |
| T-231 | Deploy F3 Cảnh báo UI (`vnstocks` only) | docker | **Master ack Pass** — image `2f18fd2c75e9`; upstream PASS; health 200; public 302 |
| T-232 | Redeploy UI from `main` (post PR #2) | docker | **Executor Done** — image `2900f583873a`; `main` @ `c5d1e6c`; upstream PASS; health 200; public 302 |

### Doing (ag2 / Exe1 — `T-*`)

| ID | Title | Status | Modules | Target files | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|--------------|------------|------|----------------------|
| — | *(trống — chờ human / ag1)* | — | — | — | — | — | — |

**Quy tắc:** tối đa **một** `T-*` Doing (ag2) **và** tối đa **một** `S-*` Doing (ag3) — hai lane song song, không chung ID.

### Todo (sẵn sàng khi human chọn) — ag2

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, … | Mentor | Mentor | **Blocked.** |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo mentor | Mentor | Mentor | **Blocked.** |
| T-222 | Brand CSS Authentik login (optional) | Blocked | infra | Authentik brand CSS | Visual brand | Human | **Blocked** — tách khỏi Sources; optional. |

### Support board (ag3 / sp1 — `S-*`)

#### Doing (ag3)

| ID | Title | Status | Modules | Target files | Acceptance | Owner |
|----|-------|--------|---------|--------------|------------|-------|
| — | *(trống)* | — | — | — | — | — |

#### Done (ag3 — gần đây)

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| **S-021** | Nâng vnstock + pull bars + refresh metrics | **Done** | **Master ack Pass** — vnstock 5.1.0; bars 180/181 (PDG miss KBS); recall 100% / prec 99.1% |
| **S-020** | Sector universe reverse-fit + gap report | **Done** | **Master ack Pass** — 33/181 bars (baseline) |
| **S-010** | F3 «Cảnh báo» — catalog rule → spec | **Done** | `docs/specs/F3_ALERTS.md` — **Master ack Pass** |

#### Todo (ag3)

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| — | *(trống)* | — | — |

---

## 5. Risks & open questions

1. ~~P0 Top KL Giá≈TC~~ — **smoke Pass** — caption Redis Giá/% 11/20; MBB/CTG/GAS khớp Realtime (19.85/−0.25, 30.6/+2.68, 76.1/−0.13).
2. ~~T-151 VNINDEX Overview~~ — **smoke Pass** — VNIndex 1,705.91 (+0.45%); caption Redis index-feed 6/6 @ 16:56:54.
3. **Mentor gate** F1 còn lại.
4. ~~WAIT inbox 1530~~ — **hết** (report trên `auditor/20261017-post-ux-wave-retest` @ `6932c76`).
5. ~~T-130 image drift~~ — hết.
6. Multi-agent: bus = PROGRESS only.
7. ~~Gemini OIDC-in-Streamlit~~ — **từ chối** (ADR 0006); Social = Authentik Sources + **pending approve**.
8. ~~OAuth / T-221~~ — Google SSO **Pass** (human); FB chưa smoke live; OIDC Skip.
9. ~~F3 S-010 + T-230~~ — **acked**; Open Q §11 defaults Exe1: close_D; tol=0 / SUPPORT_BAND swing; Telegram/màu = sau.
10. **Auto-trade pipeline** — tài liệu tham chiếu only; NON-goal: không đặt lệnh.

---

## 6. Handoff to Agent 2 (ag2 / Exe1)

**Current Doing (T-*):** *(trống)* — T-232 Done; chờ ag1 ack.

### DONE — T-232 (Exe1 → ag1) — **awaiting master_ack**

- VPS: `checkout main` + pull → `c5d1e6c` (≥ `1448cf5`)
- image `2900f583873a`; `--no-deps --force-recreate vnstocks` only
- upstream PASS; health **200**; public **302**
- Không đụng nginx/sshd/UFW/workers; không còn `feat/sector-universe-f3` trên VPS

### DONE — T-231 — **acked** (image `2f18fd2c75e9` — superseded by T-232)

### Master ack (T-231) — 2026-10-18
- **Pass** — deploy DoD đủ.

### DONE — T-230 — **acked** + shipped `a7882c7`

### Master ack (T-230) — 2026-10-18
- Pass: decision-support only; close_D + tol defaults; shipped.

### Master ack (S-010) — 2026-10-18
- `docs/specs/F3_ALERTS.md` Pass (đã ship).

### Master ack (T-221)
- Human: Google login Pass + đổi mật khẩu Pass.
- Verify: Source Google enabled; 1 connection → user `mydev` `is_active=True`; site 302.
- C Skip; FB live chưa bắt buộc.

### Master ack (T-163)
- Report Exe1: **Pass** @ 1280×800; image `4aaa437be56c`; không sửa code.
- Master không re-smoke (plan-only stance).

---

## 6b. Handoff to Agent 3 (ag3 / sp1)

**Current Doing (S-*):** *(trống)* — idle; **S-021 Master ack Pass**.

### DONE — S-021 (sp1 → ag1) — **acked**

**Deliverables:** vnstock 5.1.0; bars **180/181**; report + fitted refresh  
**Caveat chấp nhận:** PDG thiếu (KBS không có mã) — không chặn Pass.

**Acceptance**
- [x] vnstock ≥ 5.1 · coverage 180/181 · report · push
- [x] master_ack yes

### Master ack (S-021) — 2026-10-18
- **Pass** — coverage gần đủ; 14/14 theme; OUT giữ.

### DONE — S-020 — **acked** (baseline 33/181)
### DONE — S-010 — **acked**

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

Sau đó: session cũ `Status=paused_fork`; **giữ đúng một** task `Doing` **trên cùng lane** (T-* hoặc S-*).

| Tab | Alias | Turns | Files this task | Slowing? | Status |
|-----|-------|------:|----------------:|----------|--------|
| master | ag1 | — | — | — | active (plan-only) |
| executor-1 | ag2 | 1 | 1 | no | **idle — T-232 Done** |
| executor-2 | ag2 | — | — | — | standby (fork) |
| support-1 | ag3 / sp1 | 1 | 3 | no | idle — S-021 **acked** |

### Master commands

```
T-232 Done — master_ack pending.
sp1 IDLE.
```

### Last Executor state (ag2)

```
task: T-232
result: Done
image: 2900f583873a
code: c5d1e6c
branch: main
upstream: PASS
health: 200
public: 302
owner: executor-1
Status: idle
master_ack: pending
```

### Last Support state (ag3 / sp1)

```
task: S-021
result: Done
owner: sp1
Status: idle
master_ack: yes
vnstock: 5.1.0
bars_coverage: 180/181
missing: PDG (KBS)
macro_recall: 1.0
macro_precision: 0.991
report: docs/specs/F3_SECTOR_UNIVERSE.md
```

### Signals

(none)

---

## Changelog (PROGRESS)

| Khi | Thay đổi |
|-----|----------|
| 2026-10-18 | **START T-232** — redeploy vnstocks from main (human 1b) |
| 2026-10-18 | **T-232 Done** — VPS `main` @ `c5d1e6c`; image `2900f583873a`; upstream PASS; health 200; public 302 |
| 2026-10-18 | **PR #2 MERGED** — F3 → `main` @ `28b555d` (squash) |
| 2026-10-18 | **Master ack S-021 Pass** — 180/181 bars; PDG miss accepted |
| 2026-10-18 | **S-021 Done** — vnstock 5.1.0; bars 180/181; gap refresh; PDG miss KBS |
| 2026-10-18 | **NUDGE S-021** — sp1 nhầm “up-to-date” = Done; nhắc làm đủ §6b (human 1a) |
| 2026-10-18 | **START S-021** — sp1 vnstock≥5.1 + pull bars + refresh gap (human 1c) |
| 2026-10-18 | **Master ack T-231 Pass + S-020 Pass** — deploy UI + sector universe report |
| 2026-10-18 | **S-020 Done** — F3_SECTOR_UNIVERSE gap report; fitted refresh; 33/181 bars |
| 2026-10-18 | **Poll idle** — ag2/ag3 không Doing; T-230 ship `a7882c7`; bus header sync |
| 2026-10-18 | **START T-231 + S-020** — deploy UI vnstocks; sp1 sector universe (human 1d) |
| 2026-10-18 | **T-231 Done** — image `2f18fd2c75e9`; VPS `feat/sector-universe-f3` @ `9fd7d69`; upstream PASS; health 200; public 302 |
| 2026-10-18 | **Bus protocol** — human↔ag1 chỉ số; ag2/ag3 pull PROGRESS (ít paste) |
| 2026-10-18 | **Master ack T-230 Pass** — F3 alerts UI; chờ human commit |
| 2026-10-18 | **T-230 Done** — f3_alerts + Watchlist F3 cột Cảnh báo; pytest Pass (7); no deploy |
| 2026-10-18 | **START T-230** — ag2 F3 Cảnh báo UI+engine; ship S-010 docs + bus |
| 2026-10-18 | **Master ack S-010 Pass** — F3_ALERTS; T-230 unlocked |
| 2026-10-18 | **S-010 Done** — `docs/specs/F3_ALERTS.md`; Last Support idle; chờ Master ack |
| 2026-10-18 | **S-010 Doing** — Handoff §6b ag3; T-230 Todo (chờ S-010); lane T-* / S-* song song |
| 2026-10-18 | **Naming** — ag1=Master; ag2=Exe1; ag3=Support/sp1 (ghi đầu file) |
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
| 2026-10-17 | **T-161 Done** — image 8b8bba1590af; upstream PASS; health 200; Status=idle |
| 2026-10-17 | **Master ack T-161** — verify report + public health 302; ship PROGRESS |
| 2026-10-17 | **ADR 0007 Accepted** — Exe1 deploy gate `@2331fed` |
| 2026-10-17 | **T-152 visual smoke Pass** — TopKL no index; POW universe caption; PnL legend |
| 2026-10-17 | **T-153 Doing** — human 1a; owner Exe1; contrast zebra / Δ |
| 2026-10-17 | **T-153 Done** — zebra soft + skip signed + font-weight; pytest Pass (9) |
| 2026-10-17 | **Master ack T-153 (human 1b)** — ship + authorize T-162 Exe1 deploy |
| 2026-10-17 | **T-162 Phase B GO** — Exe1 deploy T-153 UI; user_confirmed_infra: yes |
| 2026-10-17 | **T-162 Done** — image `4aaa437be56c`; pull `9e6aef3`; upstream PASS; health 200; Status=idle |
| 2026-10-17 | **Master ack T-162** — verify report + public health 302; ship PROGRESS |
| 2026-10-17 | **Stance** — Master plan-only; Exe1 execute; Exe2 standby khi fork |
| 2026-10-17 | **T-163 Doing** — human 1a; Exe1 smoke contrast @ 1280×800 |
| 2026-10-17 | **T-163 Done (Pass)** — Overview/Realtime/sidebar Δ readable @ 1280×800; Status=idle |
| 2026-10-17 | **Master ack T-163** — Exe1 smoke Pass; no Master re-smoke |
| 2026-10-17 | **SSO plan** — Sources + pending approve; brief/blueprints/T-220 Doing; T-221 Todo; user_confirmed_infra: yes |
| 2026-10-17 | **T-220 Done** — blueprints + Sources on VPS; T-221 Partial; outbox 1830-DONE |
| 2026-10-17 | **T-221 Partial** — secrets sync+enable; Google UI Pass; A/B chờ human IdP; outbox 2320 |
| 2026-10-17 | **Master ack T-221 Pass** — human Google login + đổi MK; connection mydev |
