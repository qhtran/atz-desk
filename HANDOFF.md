# Handoff — F3 AI-Native SDLC (atz-desk / dev.atz.vn)

Dành cho Cursor Agent trên MacBook. Cập nhật: 2026-10-27 (Asia/Saigon).

## Vai trò

- Repo: `qhtran/atz-desk`
- Phạm vi: `backend/`, `frontend/`, `config/` ONLY
- Không đụng `src/` legacy / prod atz.vn
- Tiếng Việt, dòng `[DBG]`, lựa chọn `1a`/`1b`
- Karpathy: hỏi xác nhận trước khi sửa code

## Đã xong (Bước 1–2)

| Mục | Chi tiết |
|-----|----------|
| Files | [`intent.md`](intent.md), [`spec.md`](spec.md), file này |
| Branch | `cursor/f3-sdlc-intent-spec-9e73` |
| PR | https://github.com/qhtran/atz-desk/pull/10 (docs-only) |
| Quyết định user | **1c** — chỉ merge PR docs, **chưa** `plan.md`, **chưa** code production |

## Quyết định đã chốt trong spec

1. UI F3 accordion 5 cột trên `frontend/index.html` (iBoard) — không dùng `trading.html`
2. Cộng đồng Phase-1 = stub (“Sắp có”)
3. Alert **native** trong `backend/` (`f3_indicators.py`) — bỏ wrap `analysis.f3_alerts` legacy
4. Giữ `GET /api/portfolio/sectors/f3` + `POST /api/portfolio/alerts`
5. Không thêm `/api/trading/sectors` (paper trade)

## Việc tiếp theo (chỉ khi user bảo)

1. Xác nhận PR #10 đã merge vào `main` (hoặc merge trên Mac / GitHub)
2. `git pull origin main` (hoặc checkout branch này nếu chưa merge)
3. Nếu user duyệt spec → viết `plan.md` (Bước 3 checklist atomic) → hỏi xác nhận trước khi code
4. Code theo plan: `index.html` accordion, `portfolio_f3.py` + `f3_indicators.py`, `tests/test_portfolio_f3.py`

## Nhánh phụ (không thuộc PR #10)

- `cursor/f3-preview-html-9e73`: mock `frontend/f3-preview.html` + route `/f3-preview`
- Từng bị 403 push trên một phiên cloud; có thể chưa có trên remote
- Không gộp vào docs PR trừ khi user yêu cầu

## Pull trên Mac

```bash
git fetch origin
git checkout cursor/f3-sdlc-intent-spec-9e73
git pull origin cursor/f3-sdlc-intent-spec-9e73
# hoặc sau khi merge PR #10:
# git checkout main && git pull origin main
```

Đọc lần lượt: `HANDOFF.md` → `intent.md` → `spec.md`. Chưa viết `plan.md` / chưa code trừ khi user chọn tiếp Bước 3.
