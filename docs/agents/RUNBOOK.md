# Vận hành 2 agent — Master và Executor

Dành cho người đọc lại. Agent **không** đọc file này mỗi turn. Bus mỗi turn là [`NOW.md`](NOW.md).

**Phạm vi:** `dev.atz.vn` — `backend/`, `frontend/`, `docker-compose.dev.yml`. Prod Streamlit ngoài board.

## Hai tab

| Tab | Vai | Việc |
|-----|-----|------|
| Chat này (hoặc tab bạn gắn **Master**) | **ag1** | Plan, giao packet, ack. Không code, không SSH. |
| Tab Composer khác | **ag2 Executor** | Một task `Doing`. Sửa đúng file trong packet. |

Bạn chỉ trả lời Master bằng số (`1a`, `ack`, …). Không dán brief dài, không chuyển tin giữa hai tab.

## File nào được đọc

| File | Ai | Khi nào |
|------|----|---------|
| [`NOW.md`](NOW.md) | Cả hai | Mỗi turn. Trần khoảng 80 dòng. |
| `docs/agents/tasks/<ID>.md` | Executor | Chỉ khi Doing trên NOW đúng ID đó. |
| [`TASK_TEMPLATE.md`](TASK_TEMPLATE.md) | Master | Lúc viết packet mới. |
| [`docs/HANDOFF_NEXT_CHAT.md`](../HANDOFF_NEXT_CHAT.md) | Master | Lúc lập task mới (trạng thái sản phẩm). |
| File này | Bạn | Khi cần nhớ cách điều khiển. |
| `docs/agents/archive/` | Không ai | Trừ khi bạn nêu đúng T-id cũ (prod, đến 2026-10-20). |

`PROGRESS.md` ở root chỉ là stub. Lịch sử dài nằm trong archive.

## Mở Executor

Tab mới, dán nguyên:

```text
Pull. Đọc docs/agents/NOW.md. Nếu Doing là việc của mình, mở đúng docs/agents/tasks/<ID>.md. Không mở archive. Xong thì cập nhật NOW (5 dòng Last executor) rồi dừng.
```

Không `@` archive, không `@` HANDOFF, không `@` file này.

Doing trống thì Executor pull xong và dừng. Đó là đúng.

## Giao một việc

1. Bạn nói với Master việc cần làm (một câu, hoặc số lựa chọn).
2. Master ghi `docs/agents/tasks/<ID>.md` từ template: mục tiêu, file được sửa, DoD, ngoài phạm vi.
3. Master điền **một** dòng Doing trên NOW (ID, owner `ag2`, đường dẫn packet). Không chép brief vào NOW.
4. Commit + push bus (khi bạn bảo).
5. Bạn bảo tab Executor: pull lại (hoặc dán lại hook).

Một Doing tại một thời điểm.

## Xong việc

1. Executor sửa code, chạy test trong packet, ghi 5 dòng **Last executor** trên NOW (`task`, `result`, `status: idle`, `pytest`, `master_ack: pending`). Không viết changelog.
2. Bạn nói với Master: `ack` (hoặc số Master đưa).
3. Master đối chiếu báo cáo. Pass thì Doing về trống, chuyển packet sang `docs/agents/archive/tasks/`, `master_ack: yes`.

## Không làm

- Không để Executor đọc cả HANDOFF hay archive mỗi turn.
- Không mở tab Executor thứ hai khi tab hiện tại còn Doing.
- Không nhét lịch sử task vào NOW. NOW chỉ là bảng sống.
- Master không code và không SSH. Deploy chỉ khi packet ghi rõ và bạn xác nhận.
