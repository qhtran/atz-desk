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

**Architect đã ship code trên main** (`datasource/live_quotes.py` + sidebar Redis→OHLCV fallback + `tests/test_live_quotes.py`).

VPSbot đêm nay: **verify pytest + merge nếu thiếu + deploy `vnstocks`**. Nếu code chưa đủ / fail test → sửa nhỏ rồi deploy.

## Phạm vi file / module

- Verify: `src/atz/datasource/live_quotes.py`, `src/atz/ui/sidebar_portfolio.py`, `tests/test_live_quotes.py`
- Chỉ sửa nếu test Fail hoặc bug đơn vị giá (VND vs nghìn đồng)

## Không đụng

- nginx / SSH / firewall / Authentik / `.env`
- Filter F1 (brief `0700`)

## Done khi

1. `pytest tests/test_live_quotes.py tests/test_capital_ledger.py` Pass
2. Deploy `vnstocks` (SSH:443, `/opt/vnstocks`)
3. Outbox `…-0622-sidebar-live-quote-DONE.md` (HEAD + lệnh deploy)
4. F1 mục 2 checkbox đã tick (nếu chưa)

## Tham chiếu

- `docs/F1_CHECKLIST_UI.md` §2
- `docs/COLOR_TOKENS.md`
- `docs/architecture.md` / Redis quotes
- Auditor task song song: `docs/auditorbot/tasks/20261017-0622-f1-acceptance-baseline.md` (có thể chưa có báo cáo khi bạn bắt đầu — không chặn)

## Ghi chú VPS (SSH)

- Liên lạc: **SSH qua cổng 443**
- Host path: `/opt/vnstocks`
- Services restart: `vnstocks`
