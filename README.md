# ATZ Desk

**Tagline:** *Realtime · Tín hiệu · Một bàn.*

ATZ Desk là bàn làm việc giao dịch trên web (dev: [dev.atz.vn](https://dev.atz.vn)): bảng giá realtime, iBoard theo sàn, quét filter ngày, phân tích mã (chart). Repo GitHub: **`atz-desk`**.

Ứng dụng legacy **atz.vn** (Streamlit) vẫn có thể chạy song song trên cùng VPS; stack active dev là FastAPI + SPA trong `backend/`, `frontend/`, `docker-compose.dev.yml`.

## Glossary (tránh nhầm tên)

| Tên | Ý nghĩa |
|-----|---------|
| **ATZ Desk** | Sản phẩm / app (UI, API dev.atz.vn) |
| **iBoard** | Module bảng điện + panel phân tích mã |
| **vnstock** | Thư viện dữ liệu (gói thành viên Gold) — dùng khi **seed EOD** → `data/ohlcv`, không gọi mỗi lần mở chart |
| **priceboard** | Tên kỹ thuật nội bộ: Redis keys, WS `/ws/priceboard`, `config/priceboard.yaml` |

## Tài liệu

| File | Nội dung |
|------|----------|
| [docs/specs/IBOARD_MODULE_MAP.md](docs/specs/IBOARD_MODULE_MAP.md) | Bản đồ module ATZ Desk / iBoard (dev) |
| [docs/architecture.md](docs/architecture.md) | Kiến trúc 6 module + index feed (legacy/prod) |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Debug label, error code (prod Streamlit + ops) |
| [AGENTS.md](AGENTS.md) | Quy tắc làm việc Bot / GPC |

## Cấu trúc code (dev ATZ Desk)

- **API / WS:** `backend/` (FastAPI)
- **SPA:** `frontend/index.html`
- **Dev compose:** `docker-compose.dev.yml` (project `atz_desk`)
- Legacy Python prod: `src/atz/` — ngoài phạm vi dev trừ khi user mở lại

## Chạy nhanh (tóm tắt)

- **Dev Desk:** `docker compose -f docker-compose.dev.yml up --build` → API `http://127.0.0.1:8000`, WS `/ws/priceboard`
- **VPS dev deploy:** clone `/opt/atz-desk` (script `scripts/deploy-vps.sh dev`); prod/ingestion legacy có thể vẫn ở `/opt/vnstocks`
- **Test:** `pytest` (`testpaths=tests`)

Secret chỉ nằm trong `.env*` / `.pip_index` trên máy chạy — không commit.

## Quy tắc agent

Xem `.cursor/rules/` và `AGENTS.md`: kế hoạch → xác nhận → mới sửa; không force push; tín hiệu `pos_*` chỉ chat riêng.
