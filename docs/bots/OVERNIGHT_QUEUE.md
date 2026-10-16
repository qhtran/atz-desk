# Hàng đợi đêm (Orchestrator tự quyết)

**Trạng thái:** active — chủ repo ngủ; Cursor = kiến trúc sư; 2 bot tự poll.  
**Architect fallback:** đã code sidebar live quote trên repo (chờ VPSbot deploy).  
**HEAD lúc mở queue:** xem `git log -1` trên `main`.

## Quyết định đã khóa (bot không hỏi lại)

1. Vai trò giữ nguyên: VPSbot code/deploy; AuditorBot test web; Cursor brief + đọc kết quả.
2. Màu chuẩn FireAnt = `docs/COLOR_TOKENS.md` / `theme_tokens.py`.
3. Sidebar giá: Redis `quote:{symbol}` trước, OHLCV fallback — không block deploy nếu Redis trống (fallback + ghi Notes).
4. Filter F1 Bollinger/Ichimoku/phần II: **không** làm đêm nay (thiếu doc mentor).
5. `merge_main: yes` + `deploy: yes` cho brief deploy đã ghi; không đụng nginx/sshd.
6. Nhiều file trong hộp việc → làm **theo tên file tăng dần**, mỗi lần 1 việc, rồi poll tiếp.
7. Không hỏi user; brief mơ hồ không an toàn → `-FAIL.md` + Notes, lấy việc tiếp.

## Hàng đợi AuditorBot (`docs/auditorbot/tasks/`)

| Thứ tự | File | Mục tiêu |
|--------|------|----------|
| 1 | `20261017-0622-f1-acceptance-baseline.md` | Baseline F1 chấp nhận |
| 2 | `20261017-0630-colors-ceiling-floor.md` | Màu + trần/sàn sâu |
| 3 | `20261017-0630-rss-html.md` | Regression HTML tin |
| 4 | `20261017-0700-sidebar-retest.md` | Retest sidebar sau khi VPSbot deploy (nếu chưa deploy: ghi BLOCKED + ngày giờ) |

Chi tiết case: `docs/bots/ACCEPTANCE_TESTS.md`.

## Hàng đợi VPSbot (`docs/bots/vpsbot/inbox/`)

| Thứ tự | File | Mục tiêu |
|--------|------|----------|
| 1 | `20261017-0622-sidebar-live-quote.md` | Sidebar live quote + test + deploy `vnstocks` |
| 2 | `20261017-0630-sidebar-quote-tests.md` | Siết unit test / edge stale/missing |
| 3 | `20261017-0700-filter-f1-core.md` | Siết logic filter F1: nến đảo chiều / RSI đáy / MACD (mục 7.1–3) — không Bollinger/Ichimoku |

## Orchestrator (Cursor)

- Chỉ brief ngắn + push; **không** loop poll; **không** code thay VPSbot (tiết kiệm token).
- Khi có outbox/báo cáo → pull đọc + tóm tắt / brief tiếp nếu P0.

