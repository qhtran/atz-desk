# Task <ID> — <tiêu đề>

**Owner:** ag2  
**Status:** Doing  
**Phạm vi:** dev.atz.vn

Master điền file này lúc giao việc. Executor chỉ mở đúng packet đang Doing, không mở template.

## Mục tiêu

Một câu.

## File được sửa

- `backend/...`
- `frontend/...`
- `tests/test_<module>.py`

## DoD

- [ ] …
- [ ] pytest Pass (ghi lệnh và số)

## Ngoài phạm vi

- Prod Streamlit, nginx, SSH, secrets.
- File không liệt kê ở trên.

## Báo

Cập nhật 5 dòng Last executor trên `docs/agents/NOW.md`:

```text
task: <ID>
result: Pass|Fail — một câu
status: idle
pytest: Pass (n) | Fail
master_ack: pending
```

Không viết lại brief vào NOW.
