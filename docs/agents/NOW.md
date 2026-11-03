# NOW — bus lớp 1 (dev.atz.vn)

**Cập nhật:** 2026-11-03  
**Phạm vi:** `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml`.  
**Cutover ADR 0009:** **đóng sổ**.  
**SPA shell:** B1+B2 auth/RBAC/Alerts + **B3 Admin Control Panel** (runtime overlay + hot-reload) — **Done**.

Đọc file này mỗi turn. Không changelog. Không mở `docs/agents/archive/` trừ khi human nêu đúng T-id. Human đọc `docs/agents/RUNBOOK.md` khi cần nhớ cách điều khiển; agent không đọc file đó mỗi turn.

## Vai

| Alias | Vai | Làm | Không làm |
|-------|-----|-----|-----------|
| **ag1** | Master | Plan, giao task, ack. Ghi Doing ở đây + một file `docs/agents/tasks/<ID>.md`. | Không code, không SSH. |
| **ag2** | Executor | Một `Doing` tại một thời điểm. Sửa đúng file trong packet. | Không mở task khác, không mở template. |

## Thứ tự đọc

1. `git pull --ff-only`
2. File này.
3. Nếu Doing đúng vai mình → chỉ `docs/agents/tasks/<ID>.md`, rồi đúng file packet liệt kê.
4. Dừng. Không đọc HANDOFF trừ khi packet trỏ một mục. Master đọc `docs/HANDOFF_NEXT_CHAT.md` khi **lập task mới**.

Hook (dán nguyên khi mở tab):

```text
Pull. Đọc docs/agents/NOW.md. Nếu Doing là việc của mình, mở đúng docs/agents/tasks/<ID>.md. Không mở archive. Xong thì cập nhật NOW (5 dòng Last executor) rồi dừng.
```

## Doing

| ID | Owner | Packet | Việc |
|----|-------|--------|------|
| — | — | — | idle |

## Todo

| ID | Việc | Ghi chú |
|----|------|---------|
| — | Risk YAML số thật | Hiến điền `trading_station.yaml` null (SL/TP/equity) — Admin overlay B3 có thể tạm ghi risk placeholders |

## Master commands

```text
idle
```

## Milestone (done)

```text
2026-11-03 ADR 0009 cutover Desk SPA — CLOSED:
P0/activate — prod-desk :8001 + nginx atz.vn → atz-desk-api
P3 — verify Risk YAML scaffold + atz_prod_data portfolio parity (null risk chờ Hiến) · master_ack · archived
P4 — tắt UI Streamlit vnstocks :8501 (script decommission; bots giữ nguyên) · master_ack · archived
Option B — /ws/stream/alerts + mock_tick_generator smoke Pass · master_ack · archived
Infra — Redis stream listener + Desk SPA FastAPI (prod/dev tách data)
SPA B1+B2 — auth welcome / Alerts tab / Admin RBAC guard · merged main @ 6733f7c
SPA B3 — Admin Control Panel GET/PUT + overlay + hot-reload · PR #15 · main @ 930b8e8 · master_ack · archived
```

## Last executor

```text
task: T-admin-control-panel-b3
result: Pass — master_ack; packet → docs/agents/archive/tasks/; deploy smoke OK
status: idle
pytest: Pass (admin control plane + RBAC)
master_ack: done 2026-11-03
```

Khi ack: Doing về trống; chuyển packet sang `docs/agents/archive/tasks/`. Không chép brief vào file này.
