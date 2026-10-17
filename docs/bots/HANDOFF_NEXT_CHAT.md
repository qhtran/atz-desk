# Handoff — mở chat Cursor mới (2026-10-17)

**Đọc file này trước** khi code. Orchestrator = Cursor (tự code/deploy). Bot code **paused**; giữ **AuditorBot** (survey hình). SSH dual-path: Mac `:22`, VPSBot dự phòng `:443`/`rd.atz.vn`.

**HEAD lúc handoff:** kiểm `git log -1` trên `main` (kỳ vọng ≥ `604b51b` OAH copy + flash + pin + vốn SQLite).

---

## Đã chốt (không mở lại trừ chủ repo)

| Chủ đề | Quyết định |
|--------|------------|
| Auth | Forward-auth Authentik; identity = header; Account Phase 1 headers-only |
| Dữ liệu | Bền → SQLite; nóng → Redis; test → tmp/fixtures (`docs/adr/0005-…`) |
| Trading profile | **Không** bảng TEXT-PK Gemini; dùng `user_capital_ledgers` + `cai_dat_chung.trading_profile` (`docs/adr/0004-…`) |
| FE lớn | Giữ Streamlit; không SPA/BFF Phase 2 trừ nhu cầu mới |
| Bot | Cursor làm code; Auditor = UI/hình; VPSBot paused (giữ SSH:443 ops) |
| Mạng | `docs/infrastructure/VPS_NETWORK.md` — **cấm** đụng stream/sshd/UFW trừ confirm |

---

## Đã xong gần đây (production đã deploy qua `:22`)

- Sidebar live quote Redis + fallback OHLCV  
- Filter F1 nến/RSI/MACD (`mode=f1`)  
- Account UX Phase 1 (Tài khoản + logout outpost)  
- Vốn + risk **per-user** SQLite (`datasource/user_trading.py`)  
- **Pin** mã (`pinned_symbols`) + cột Ghim trên realtime  
- Flash realtime mạnh hơn (`flash_min_tick_vnd`, `flash_hold_cycles`)  
- Copy lệnh chuẩn OAH: `MÃ: … \| HÀNH ĐỘNG: … \| KL \| GIÁ (nghìn) \| SL \| TP`

---

## Việc còn lại (ưu tiên)

### P0 / UX đang chờ duyệt

**User Dashboard «Không gian Trading»** (Gemini) — kế hoạch đã trình, **chưa code**, chờ chọn:

1. `ui/trading_workspace_page.py` — Vốn&Risk · Filter defaults · Pin + **Lưu toàn bộ**  
2. Mở rộng `user_trading` (`min_roe`, `min_klgd`, `min_rs`, RSI/MACD prefs)  
3. Wire `pages.py` (tab mới **hoặc** gộp vào Tài khoản — user chưa chốt 1a/1c)  
4. Thu gọn sidebar (chỉ đọc + link sửa)  
5. **Fix cột Ghim:** `*` thay `★`; thêm `Ghim` vào `key_cols` Glance  

Lựa chọn đã đề xuất (chat cũ):  
- `1a` A→B→C full  
- `1b` chỉ fix Ghim  
- `1c` gộp vào tab Tài khoản  

### P1 khác

- Wire filter prefs vào Bộ lọc / sidebar đọc từ SQLite (sau workspace)  
- Rebuild image lệch: ingestion / index / alert / position + `atz-check-upstream`  
- Nến mạnh/TB/yếu — chờ mentor  

### P2 / chặn mentor–infra

- Bollinger / Ichimoku / phần II (F1)  
- Brand CSS Authentik  
- Dọn n8n exited; fail2ban Authentik; alert cert  
- Auditor tasks còn trong `docs/auditorbot/tasks/` — inbox báo cáo vẫn trống  

---

## File quan trọng

| Path | Việc |
|------|------|
| `docs/bots/BOTS_ROSTER.md` | Vai trò bot |
| `docs/infrastructure/VPS_NETWORK.md` | Mạng / SSH |
| `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md` | Account Phase 1/2 |
| `docs/adr/0004-*.md`, `0005-*.md` | Profile + data placement |
| `src/atz/datasource/user_trading.py` | Vốn/risk/pin |
| `src/atz/ui/realtime_page.py` | Board, pin, flash |
| `src/atz/order_helper/core.py` | Copy lệnh |
| `src/atz/ui/account_page.py` | Tài khoản IdP |

---

## Quy tắc chat mới

1. `git pull --ff-only origin main`  
2. Tiếng Việt + `[DBG]` + lựa chọn `1a/1b…` khi hỏi  
3. Tự chạy lệnh trong repo; **cấm** file ngoài project  
4. Deploy VPS: SSH **`:22`** `root@112.213.88.230` → `/opt/vnstocks` build/up `--no-deps vnstocks`  
5. Không force push; không đụng nginx stream  

**Prompt gợi ý mở chat:**  
«Đọc `docs/bots/HANDOFF_NEXT_CHAT.md`. Tiếp việc Không gian Trading + fix cột Ghim theo lựa chọn tôi gửi.»
