# Handoff — mở chat Cursor mới (2026-10-17)

**Đọc file này trước** khi code. Orchestrator = Cursor (tự code/deploy). Bot code **paused**; giữ **AuditorBot** (survey hình). SSH dual-path: Mac `:22`, VPSBot dự phòng `:443`/`rd.atz.vn`.

**HEAD lúc handoff:** kiểm `git log -1` trên `main` (kỳ vọng ≥ `cf68947` — table variants + pin strip + trading workspace).

**Theo dõi tiến độ:** `PROGRESS.md` (root) — Architect cập nhật task board / Handoff Agent 2.

---

## Đã chốt (không mở lại trừ chủ repo)

| Chủ đề | Quyết định |
|--------|------------|
| Auth | Forward-auth Authentik; identity = header; Account Phase 1 headers-only; **cấm** OIDC Client Streamlit (ADR 0006); Social = Authentik Sources (brief infra) |
| Dữ liệu | Bền → SQLite; nóng → Redis; test → tmp/fixtures (`docs/adr/0005-…`) |
| Trading profile | **Không** bảng TEXT-PK Gemini; dùng `user_capital_ledgers` + `cai_dat_chung.trading_profile` (`docs/adr/0004-…`) |
| FE lớn | Giữ Streamlit; không SPA/BFF Phase 2 trừ nhu cầu mới |
| Bot | Cursor làm code; Auditor = UI/hình; VPSBot paused (giữ SSH:443 ops) |
| Mạng | `docs/infrastructure/VPS_NETWORK.md` — **cấm** đụng stream/sshd/UFW trừ confirm |
| UI bảng | Mọi bảng qua `render_data_table(variant=realtime\|analytical\|compact)` — `docs/COLOR_TOKENS.md` |

---

## Đã xong gần đây (production / main)

- Sidebar live quote Redis + fallback OHLCV  
- Filter F1 nến/RSI/MACD (`mode=f1`)  
- Account UX Phase 1 (Tài khoản + logout outpost)  
- Vốn + risk **per-user** SQLite (`datasource/user_trading.py`)  
- **Pin** mã (`pinned_symbols`) + live pinned strip trên board (`1a1dde5`)  
- Flash realtime mạnh hơn (`flash_min_tick_vnd`, `flash_hold_cycles`)  
- Copy lệnh chuẩn OAH: `MÃ: … \| HÀNH ĐỘNG: … \| KL \| GIÁ (nghìn) \| SL \| TP`  
- **Trading workspace** tab Done (`c71dc2c`): Vốn&Risk · Filter defaults · Pin · Lưu toàn bộ · Ghim glance  
- **3 table variants** Done (`cf68947`): `render_data_table` unify  
- Debug overlay + COL/ROW chips (kill-switch YAML)

---

## Việc còn lại (ưu tiên)

### P0 / UX tiếp theo (xem `PROGRESS.md` T-110…T-140)

- Wire filter prefs workspace → Bộ lọc / sidebar đọc SQLite nhất quán (T-120)  
- Verify không còn bảng bypass theme (T-110)  
- Auditor: thu hoạch tasks cũ / brief retest (T-140) — inbox đang trống  

### P1 khác

- Rebuild image lệch: ingestion / index / alert / position + `atz-check-upstream` (T-130 — cần confirm SSH `:22`)  
- Nến mạnh/TB/yếu — chờ mentor (T-200)  

### P2 / chặn mentor–infra

- Bollinger / Ichimoku / phần II (F1) — T-210  
- Brand CSS Authentik + Social Sources (Google/FB) — brief `docs/infrastructure/AUTHENTIK_SOCIAL_SOURCES_BRIEF.md`; **không** Executor OIDC app  
- Dọn n8n exited; fail2ban Authentik; alert cert — T-220 (`user_confirmed_infra: yes`)  
- Auditor tasks còn trong `docs/auditorbot/tasks/`  

---

## File quan trọng

| Path | Việc |
|------|------|
| `PROGRESS.md` | Task board Architect ↔ Agent 2 |
| `docs/bots/BOTS_ROSTER.md` | Vai trò bot |
| `docs/infrastructure/VPS_NETWORK.md` | Mạng / SSH |
| `docs/specs/ACCOUNT_UX_AUTHENTIK_BFF.md` | Account Phase 1/2 |
| `docs/adr/0004-*.md`, `0005-*.md`, `0006-*.md` | Profile + data placement + no OIDC client |
| `docs/infrastructure/AUTHENTIK_SOCIAL_SOURCES_BRIEF.md` | Social Login trên Authentik (infra) |
| `docs/COLOR_TOKENS.md` | Màu + 3 table variants |
| `src/atz/datasource/user_trading.py` | Vốn/risk/pin/prefs |
| `src/atz/ui/trading_workspace_page.py` | Không gian Trading |
| `src/atz/ui/realtime_page.py` | Board, pin, flash |
| `src/atz/ui/components.py` / `table_theme.py` | `render_data_table` |
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
«Đọc `PROGRESS.md` + `docs/bots/HANDOFF_NEXT_CHAT.md`. Tiếp slice Todo (T-110 / T-120 / T-140) theo lựa chọn tôi gửi.»
