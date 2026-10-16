# Task AuditorBot — colors + ceiling/floor

- **ID:** `20261017-0630-colors-ceiling-floor.md`
- **Từ:** Orchestrator (overnight)
- **Ưu tiên:** P0
- **Phụ thuộc:** Nên làm sau baseline `0622` (hoặc gộp nếu cùng phiên)

---

## Mục tiêu

Kiểm sâu case **A1–A5** trong `docs/bots/ACCEPTANCE_TESTS.md` trên atz.vn vs fireant.vn.

## Phạm vi

- atz: Realtime + Tổng quan (thẻ chỉ số nếu có)
- fireant: `/thi-truong` + 1 mã đang trần hoặc sàn nếu tìm được; không có thì ghi «không quan sát trần/sàn phiên này»

## Done khi

Push `docs/auditorbot/inbox/20261017-0630-atz-colors-ceiling-floor.md` đủ bảng A1–A5 + tối đa 5 action.
