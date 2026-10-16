# Brief VPSbot — sidebar live quote

- **ID:** `20261017-0622-sidebar-live-quote.md`
- **Từ:** Cursor Orchestrator (kiến trúc sư)
- **Ưu tiên:** P1
- **deploy:** yes
- **merge_main:** yes
- **infra:** no
- **user_confirmed_infra:** no

---

## Mục tiêu

F1 mục 2 còn mở: **giá hiện tại** trên sidebar «Tổng quan vị thế» dùng quote nóng (Redis `quote:{symbol}` / pipeline hiện có), không chỉ cache OHLCV đóng cửa. Cập nhật P&L / màu theo token FireAnt nếu đã có helper.

## Phạm vi file / module

- `src/atz/ui/sidebar_portfolio.py` (và helper datasource/redis quote nếu thiếu)
- Có thể đụng nhẹ: `datasource/*` quote reader, `theme_tokens` / style số
- Test: `tests/test_sidebar_portfolio.py` hoặc `tests/test_<module>.py` mới nếu chưa có
- Config: chỉ `config/*.yaml` nếu cần TTL/key — **không** hardcode secret

## Không đụng

- nginx / SSH / firewall / Authentik / `.env`
- Viết lại toàn bộ capital ledger
- Broadcast `pos_*` ra channel
- Scope filter F1 (nến/RSI/MACD) — wave sau, chờ báo cáo Auditor nếu cần

## Done khi

1. Sidebar đọc giá live từ Redis (fallback OHLCV nếu thiếu key — ghi rõ trong outbox)
2. Test module Pass
3. Merge `main` + deploy service `vnstocks` (SSH:443, `/opt/vnstocks`)
4. Outbox `docs/bots/vpsbot/outbox/20261017-0622-sidebar-live-quote-DONE.md` (hoặc `-FAIL.md`)
5. Cập nhật checkbox F1 mục 2 trong `docs/F1_CHECKLIST_UI.md` nếu xong

## Tham chiếu

- `docs/F1_CHECKLIST_UI.md` §2
- `docs/COLOR_TOKENS.md`
- `docs/architecture.md` / Redis quotes
- Auditor task song song: `docs/auditorbot/tasks/20261017-0622-f1-acceptance-baseline.md` (có thể chưa có báo cáo khi bạn bắt đầu — không chặn)

## Ghi chú VPS (SSH)

- Liên lạc: **SSH qua cổng 443**
- Host path: `/opt/vnstocks`
- Services restart: `vnstocks`
