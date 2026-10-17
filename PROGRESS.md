# PROGRESS.md — atz.vn / vnstocks

> Master Architect artifact. Agent 2 (Code Executor) chỉ làm đúng task `Doing` trong mục Handoff.
> Cập nhật: **2026-10-17** — T-100 Done (sync HANDOFF + PROGRESS với HEAD).

---

## 1. Project snapshot

| Mục | Giá trị |
|-----|---------|
| Stack | Python 3.13, Streamlit (`src/atz/app.py`), `PYTHONPATH=src/atz` |
| Data | Redis (nóng) + SQLite `data/signals.db` (bền); secrets chỉ env |
| Deploy | Docker Compose `/opt/vnstocks` — services: `vnstocks`, ingestion, filter-runner, alert, position, index-feed, redis |
| Auth | Authentik forward-auth; identity = headers; trading prefs = SQLite (ADR 0004) |
| Branch / HEAD | `main` @ `cf68947` — `refactor(ui): unify tables into 3 render_data_table variants` (đã `git pull --ff-only`, sync `origin/main`) |
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

**Đã ship gần đây (không mở lại trừ bug):**
- Pin + live pinned strip; flash tick; OAH copy string; vốn/risk per-user.
- Trading workspace tab + filter prefs SQLite (`trading_workspace_page.py`, `user_trading.py`) — **Done**.
- Unify tables → 3 variants (`cf68947`) — **Done**.
- F1 filter mode nến/RSI/MACD (catalog + logic hàng 1–3).

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

### Todo (sẵn sàng khi human chọn)

| ID | Title | Status | Modules | Target files (dự kiến) | Acceptance | Deps | Agent 2 instructions |
|----|-------|--------|---------|------------------------|------------|------|----------------------|
| T-110 | Verify không còn bảng bypass theme | Todo | ui, tests | `src/atz/ui/**`, `tests/test_table_theme.py` | Grep: ngoài wrapper `render_data_table` không còn `st.dataframe` “thô” ở pages; test Pass | T-060 | Audit + sửa **chỉ** chỗ bypass còn sót (nếu có). Không đổi semantics bảng. Không đụng ingestion/infra. |
| T-120 | Wire prefs workspace → Bộ lọc / sidebar (đọc SQLite nhất quán) | Todo | ui, datasource | `pages.py`, `filters_page.py`, `sidebar_portfolio.py`, `user_trading.py`, `tests/test_user_trading.py` | Session start + sau Lưu: sidebar/filter dùng cùng prefs SQLite; không ghi DB mỗi tick realtime | T-040 | Một vertical slice prefs. Không thêm cột schema mới trừ khi thiếu field đã mô tả. Test Pass/Fail báo rõ. |
| T-130 | Deploy hygiene: rebuild services lệch image | Todo | docker | Compose tại VPS `/opt/vnstocks` (không sửa nginx) | Services ingestion/index/alert/position chạy image mới nếu human xác nhận lệch; `atz-check-upstream` OK nếu có | Human confirm SSH | **Chỉ** `docker compose build/up --no-deps <svc>` qua `:22`. Không đụng stream/sshd/UFW. Không force-push. |
| T-140 | Auditor: thu hoạch / đóng task cũ hoặc brief retest mới | Todo | docs | `docs/auditorbot/tasks/*`, `inbox/`, `reports/` | Inbox trống đã xử lý (archive hoặc brief mới); 1 task P0 rõ ràng nếu cần survey | — | Docs only trong `docs/auditorbot/`. Không code app. |
| T-200 | F1: enum nến mạnh / TB / yếu gắn filter | Blocked | filters, analysis, ui | `filters/candle.py`, `analysis/candles*`, `filter_criteria.py`, tests | Mentor chốt định nghĩa → unit test + catalog | Mentor | **Blocked.** Không đoán ngưỡng. |
| T-210 | F1: Bollinger / Ichimoku / phần II | Blocked | filters, analysis | theo doc mentor | Spec mentor đủ → implement từng indicator 1 PR | Mentor | **Blocked.** |
| T-220 | Brand CSS Authentik / infra soft (n8n, fail2ban, cert) | Blocked | infra | deploy Authentik / VPS | Human `user_confirmed_infra: yes` trước mọi đụng auth/nginx | Human | **Blocked** trừ confirm tường minh. |

### Doing

_Không có — chờ human chọn slice tiếp (T-110 / T-120 / T-140 / …)._

---

## 5. Risks & open questions

1. **Auditor inbox trống** dù nhiều task trong `tasks/` — survey có thể stalled; đừng giả định baseline UI đã audit.
2. **Mentor gate** cho nến mạnh–TB–yếu + BB/Ichi — không tự invent.
3. **Image drift** trên VPS (chỉ rebuild `vnstocks` gần đây?) — cần human xác nhận trước T-130.
4. **Multi-agent:** Architect không viết production code; Agent 2 chỉ 1 task `Doing` / lần.
5. ~~HANDOFF lệch workspace~~ — **đã hết** sau T-100.

---

## 6. Handoff to Agent 2

**Current Doing: none — waiting on human.**

Gợi ý slice tiếp (human chọn `1a`…):

```
1a) T-110 — Audit bảng bypass theme
1b) T-120 — Wire prefs SQLite nhất quán
1c) T-140 — Auditor tasks / inbox
1d) T-130 — Deploy hygiene (cần confirm SSH)
1e) Chờ — không giao Agent 2
```

---

## Changelog (PROGRESS)

| Khi | Thay đổi |
|-----|----------|
| 2026-10-17 | Tạo file; snapshot HEAD `cf68947`; T-010…T-060 Done; Todo T-100…T-140; Blocked T-200…T-220 |
| 2026-10-17 | **T-100 Done** — sync HANDOFF + PROGRESS; Trading workspace / pin strip / 3 variants = Done |
