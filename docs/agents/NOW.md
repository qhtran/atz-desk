# NOW — bus lớp 1 (dev.atz.vn)

**Cập nhật:** 2026-11-03  
**Phạm vi:** `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml`. Prod Streamlit ngoài board.

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
| — | — | — | trống |

## Todo

| ID | Việc | Ghi chú |
|----|------|---------|
| — | — | Human: điền YAML + commit/push (gồm nginx 2C) + deploy-dev → rồi wake Option B |

## Master commands

```text
idle
```

## Milestone (done)

```text
chuỗi 3 trục xong trên branch cursor/daily-signals-vector-baf6:
1) Data Ingestion — slim WS ticks + enrichDepth gate
2) Quant Engine — daily_signals vectorized RSI/Bollinger/ma/volume
3) Infra/Docker Edge — nginx :8080 + FE relative /api /ws (T-step5)
```

## Last executor

```text
task: T-phase3a-risk-advisor
result: Pass — scaffold Done; IDLE chờ Hiến/bạn điền YAML + deploy
status: idle
pytest: Pass (14)
master_ack: yes (4c — wake sau khi deploy để làm Option B)
```

Khi ack: Doing về trống; chuyển packet sang `docs/agents/archive/tasks/`. Không chép brief vào file này.
