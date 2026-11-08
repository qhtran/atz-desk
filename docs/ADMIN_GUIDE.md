# Admin Guide — Bản tin sáng (dev.atz.vn)

Hướng dẫn ngắn vận hành **Admin Watchbook + Bản tin sáng** trên stack `docker-compose.dev.yml`.  
Không thao tác lên prod-desk (`:8001`) trừ khi được yêu cầu rõ.

---

## 1. Tổng quan

| Mode | Khi nào | Hành vi |
|---|---|---|
| **Mode 1 — Rule-based** | `ai_mode_enabled=false` (mặc định) | Template Python + F3 (BB/Ichimoku D/W/M). Không cần API key. |
| **Mode 2 — Gemini AI** | `ai_mode_enabled=true` | Sinh draft Mode 1 → Gemini biên tập (văn phong Hiến). Lỗi API → **fallback Mode 1**, không crash. |

**Trigger**

- Cron host **06:00** T2–T6 (`Asia/Ho_Chi_Minh`): `python -m backend.morning_brief` trong container `api`.
- Admin: nút **Chạy bản tin ngay** (`POST /api/admin/briefs/run` hoặc alias `/api/admin/generate-brief`).

**Lưu trữ** (`SIGNALS_DB_PATH` → `data/signals.db`)

- `brief_configs` — enabled, macro_override, AI flags…
- `watchlist_portfolio` — danh mục curated
- `daily_briefs` — bản tin theo ngày (`body_json.engine`: `rule` \| `gemini` \| `gemini_fallback_rule` \| `rule_missing_key`)
- **Tích lũy vĩnh viễn:** mỗi ngày một dòng; **không** có job tự xóa lịch sử. Cùng ngày chạy lại = `UPSERT` ghi đè bản của ngày đó; các ngày khác giữ nguyên để tra cứu.
- Mode 2 thành công (`engine=gemini`): tiêu đề tự gắn hậu tố ` [AI Assisted]` (Mode 1 / fallback giữ tiêu đề truyền thống).

Xem thêm flowchart & crontab: mục Dual Mode trong bản trước / [`morning_brief_crontab.example`](morning_brief_crontab.example).

---

## 2. Admin Panel (UI)

Đăng nhập admin → tab **Admin**.

### 2.1 Bản tin sáng · Cấu hình

| Ô UI | Trường | Ý nghĩa |
|---|---|---|
| Tự động publish | `enabled` | Tắt → CLI/cron/`run` trả `ERR-BRIEF-010` |
| Ghi chú vĩ mô | `macro_override` | Có text → ghi đè khối vĩ mô; trống → rule VNINDEX |

### 2.2 Trợ lý AI (Gemini) — chuyển Mode

| Ô UI | Trường | Ý nghĩa |
|---|---|---|
| Kích hoạt Chế độ AI | `ai_mode_enabled` | Bật = Mode 2 |
| Gemini API Key | `gemini_api_key` | Tuỳ chọn. Ưu tiên SQLite; không thì env container `GEMINI_API_KEY`. Để trống khi lưu = **không đổi** key cũ. Nút xoá key → `__CLEAR__`. |
| Temperature | `ai_temperature` | 0.1–1.0 (mặc định 0.7) |

**Ops khuyến nghị:** đặt key trong `/opt/atz-desk/.env` (compose inject), không commit secret. Model: env `GEMINI_MODEL` (mặc định `gemini-flash-lite-latest`).

GET `/api/admin/briefs/config` **mask** key (`••••xxxx` + `gemini_api_key_set`).

### 2.3 Watchbook (JSON)

`PUT /api/admin/briefs/watchbook` — mảng object:

| Trường | Ý nghĩa |
|---|---|
| `symbol` | Mã CK (bắt buộc) |
| `buy_price` | Giá mua (VNĐ) |
| `buy_date` | Ngày mua (`YYYY-MM-DD`) |
| `stop_loss` | Giá cắt lỗ tuyệt đối (không dùng %) |
| `resistance` | Giá kháng cự |
| `status` | `giu` \| `cham_cat_lo` \| `cham_khang_cu` \| `dong` \| `theo_doi` |
| `note` | Ghi chú nội bộ |

Ánh xạ tên hay nhầm: `stop_loss_pct` → dùng `stop_loss`; `action_status` → dùng `status`.

**Ví dụ hợp lệ**

```json
[
  {
    "symbol": "FPT",
    "buy_price": 95000,
    "buy_date": "2026-10-01",
    "stop_loss": 88000,
    "resistance": 105000,
    "status": "giu",
    "note": "Core IT"
  }
]
```

### 2.4 Kiểm duyệt trước 06:00

1. Lưu watchbook / macro / (tuỳ chọn) bật AI.  
2. **Chạy bản tin ngay**.  
3. Tab **Tin tức** — Markdown đã render HTML; hard-refresh nếu cache.  
4. Cùng ngày chạy lại = ghi đè `daily_briefs`.

---

## 3. Checklist Mode 2 trên VPS

1. `.env` có `GEMINI_API_KEY=...` (không commit).  
2. `docker compose -f docker-compose.dev.yml up -d api --force-recreate` để container nhận env.  
3. Trong container: `GEMINI_API_KEY` len > 0 (không in giá trị).  
4. Admin bật AI → Chạy bản tin → `body_json.engine` kỳ vọng `gemini`.  
5. Nếu model 404/503: thử `GEMINI_MODEL=gemini-flash-lite-latest` (đã verify trên key dev) rồi recreate api.  
6. Tắt AI hoặc xoá key → engine `rule` / `rule_missing_key` / fallback — app không 500.

---

## 4. Mã lỗi nhanh

| Mã | Ý nghĩa |
|---|---|
| `ERR-BRIEF-010` | `enabled=false` |
| `ERR-BRIEF-011` | Thiếu OHLCV index |
| `ERR-BRIEF-020` | Chưa có brief |
| `ERR-BRIEF-030…033` | Lỗi gọi Gemini → fallback Mode 1 |
| `ERR-BRIEF-034` | Bật AI nhưng thiếu key |

---

## 5. File neo

- Engine: `backend/morning_brief.py`, `backend/morning_brief_ai.py`
- Store/API: `backend/morning_brief_store.py`, `backend/routers/briefs.py`
- UI: `frontend/index.html` (Admin + Tin tức)
- Journal: [`TECH_JOURNAL.md`](TECH_JOURNAL.md)
