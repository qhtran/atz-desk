# Quy tắc làm việc (Bot + GPC)

## Tên sản phẩm (glossary)

- **ATZ Desk** — app dev.atz.vn (`backend/`, `frontend/`, repo `atz-desk`).
- **iBoard** — module bảng điện UI; debug id `pb-ui:iboard.*`.
- **vnstock** — thư viện dữ liệu (Gold); **không** đồng nghĩa repo. Seed OHLCV: `backend/ohlcv_seed.py`.
- **priceboard** — tên kỹ thuật (Redis, WS path, YAML config); giữ khi sửa ingestion.

## 0. Tài liệu
- Kiến trúc / vận hành: `docs/architecture.md`, `docs/troubleshooting.md`
- Target layout (chưa bắt buộc refactor): `docs/adr/0001-target-folder-layout.md`
- **Phạm vi active dev (2026-10-25):** chỉ **dev.atz.vn** (`backend/`, `frontend/`, `docker-compose.dev.yml`). Không bàn/phát triển prod atz.vn trừ khi user yêu cầu lại — chi tiết `.cursor/rules/dev-atz-scope.mdc`.

## 1. Karpathy rules
- Code rõ ràng, modular, dễ đọc.
- Ưu tiên đơn giản và explicit.
- Tách config ra khỏi logic.
- Mỗi module một trách nhiệm.

## 2. Quy trình trước khi sửa code
- Có kế hoạch ngắn (làm gì, sửa file nào, vì sao).
- Suy luận và giải thích cách làm.
- Hỏi xác nhận trước khi triển khai.
- Chỉ sửa code sau khi được đồng ý.

## 3. Đồng bộ Git
- Pull trước khi sửa.
- Commit + push sau khi hoàn thành một phần nhỏ.
- Tránh conflict giữa Bot và GPC.
- Không force push.

## 4. Nguyên tắc chung
- Không tự ý thêm tính năng lớn hoặc thay đổi cấu trúc khi chưa được yêu cầu.
- Ưu tiên giữ app luôn chạy được sau mỗi thay đổi.

## 5. Debug tags (mọi chat)
- Mọi phản hồi agent bắt đầu bằng:
  `[DBG] intent=<...> | modules=<...> | files=<...> | conf=<low|med|high>`
- `intent`: understand | plan | ask | code | verify | git | blocked
- Khi hỏi user: luôn đưa lựa chọn sẵn (`1a`, `1b`, `2c`…) — user chỉ cần trả lời số, không phải gõ tag.
- Chi tiết: `.cursor/rules/debug-tags.mdc`
