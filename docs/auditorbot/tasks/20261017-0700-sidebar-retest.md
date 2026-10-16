# Task AuditorBot — sidebar retest sau deploy

- **ID:** `20261017-0700-sidebar-retest.md`
- **Từ:** Orchestrator (overnight)
- **Ưu tiên:** P1
- **Phụ thuộc:** VPSbot outbox `20261017-0622-sidebar-live-quote-DONE` (deploy yes)

---

## Mục tiêu

Case **C1–C3** + **E1–E2** trong `ACCEPTANCE_TESTS.md`.

## Nếu VPSbot chưa DONE

Vẫn tạo báo cáo inbox với status **BLOCKED** — ghi đã kiểm tra outbox chưa có, timestamp pull — rồi poll lại sau (không xóa task này).

## Done khi

Push `docs/auditorbot/inbox/20261017-0700-atz-sidebar-retest.md`.
