# Task AuditorBot — F1 acceptance baseline

- **ID:** `20261017-0622-f1-acceptance-baseline.md`
- **Từ:** Cursor Orchestrator (kiến trúc sư)
- **Ưu tiên:** P0
- **Vai trò:** Tester / survey chấp nhận — **không** sửa code

---

## Mục tiêu survey

Baseline kiểm thử chấp nhận UI F1 trên production **atz.vn** so với **fireant.vn**: màu giá, trần/sàn, bảng realtime, sidebar vị thế, Top KL, RSS. Ghi lệch đo được + P0/P1/P2/BLOCKED.

## Phạm vi trang

- atz.vn: Tổng quan, Realtime (bảng giá), Bộ lọc tín hiệu (Tiêu chí lọc), Tin tức/RSS nếu có; sidebar «Tổng quan vị thế»
- fireant.vn: `/thi-truong` + một trang mã (vd. `/ma-chung-khoan/VIC`) làm chuẩn màu / mật độ bảng

## Checklist bắt buộc trong báo cáo

1. Màu tăng/giảm/TC/trần/sàn (đối chiếu `docs/COLOR_TOKENS.md` nếu nhìn thấy trên UI)
2. Search mã trên bảng realtime (có/không, UX)
3. Flash / cập nhật giá cảm nhận được hay không
4. Sidebar: có đủ vốn / vị thế / cảnh báo không; giá hiện tại có “sống” không
5. Top KL phiên trên Tổng quan
6. RSS/tin: còn lộ HTML thô không
7. Mobile vs desktop: mật độ bảng (1 đoạn)

## Done khi

1. Push `docs/auditorbot/inbox/20261017-0622-atz-f1-acceptance-baseline.md` (bám `REPORT_TEMPLATE.md`)
2. Tối đa 5 đề xuất hành động đo được cho Architect → giao VPSbot sau
3. Không đụng code / nginx / secret
