# Task AuditorBot — retest sau UX wave (pin / workspace / bảng)

- **ID:** `20261017-1530-post-ux-wave-retest.md`
- **Từ:** Cursor Orchestrator (T-140)
- **Ưu tiên:** P0
- **Vai trò:** Survey UI — **không** sửa code
- **HEAD kỳ vọng:** ≥ `d19ef30` (filter prefs seed) + pin strip + trading workspace

---

## Mục tiêu survey

So sánh **atz.vn** vs **fireant.vn** sau đợt UX: bảng 3 variants, pinned strip, Không gian Trading, sidebar quote. Ghi lệch đo được + P0/P1/P2/BLOCKED theo `REPORT_TEMPLATE.md` + `docs/COLOR_TOKENS.md`.

## Phạm vi trang

- atz.vn: Realtime (bảng giá + ghim), Tổng quan (Top KL), sidebar vị thế, tab **Không gian Trading** (smoke), Tin tức/RSS (1 check HTML thô)
- fireant.vn: `/thi-truong` + một trang mã (vd. `/ma-chung-khoan/VIC`) làm chuẩn màu / mật độ

## Checklist bắt buộc

1. Realtime: màu ± / TC / trần / sàn; flash tick; **pinned strip** sống; search mã
2. Tổng quan: Top KL phiên
3. Sidebar: vị thế / giá hiện tại (Redis quote) có “sống”
4. Tab **Không gian Trading**: có/không; form Vốn·Risk·Filter defaults smoke (không cần Lưu)
5. RSS/tin: còn lộ HTML thô không (1 check ngắn)
6. Mobile vs desktop: mật độ bảng (1 đoạn)

## Done khi

1. Push `docs/auditorbot/inbox/20261017-1530-atz-post-ux-wave-retest.md` (bám `REPORT_TEMPLATE.md`)
2. Tối đa 5 đề xuất hành động đo được
3. Không đụng code / nginx / secret
4. **Không** làm các task `stale_no_inbox` trong `docs/auditorbot/BACKLOG.md`
