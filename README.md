# atz.vn / vnstocks

Ứng dụng Streamlit theo dõi, sàng lọc và cảnh báo realtime cổ phiếu Việt Nam. Web sau Authentik (`auth.atz.vn`). Không đặt lệnh tự động.

## Tài liệu

| File | Nội dung |
|------|----------|
| [docs/architecture.md](docs/architecture.md) | Kiến trúc 6 module + index feed |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Debug label, error code, health, sự cố |
| [docs/adr/0001-target-folder-layout.md](docs/adr/0001-target-folder-layout.md) | Target tổ chức thư mục (deferred) |
| [AGENTS.md](AGENTS.md) | Quy tắc làm việc Bot / GPC |

## Chạy nhanh (tóm tắt)

- **Local:** dùng venv + Streamlit (`app.py`); Redis hostname `redis` cần Docker network như trên VPS.
- **VPS:** code `/opt/vnstocks`, `docker compose` (image chung `vnstocks-vnstocks`), services `vnstocks`, `atz-ingestion`, `atz-filter-runner`, `atz-alert`, `atz-position`, `atz-index`, `atz-redis`.
- **Test:** `pytest` (`pythonpath=.`, `testpaths=tests`). Trên VPS xem lệnh trong troubleshooting / handoff.

Secret chỉ nằm trong `.env*` / `.pip_index` trên máy chạy — không commit.

## Cấu trúc code

- Code Python: `src/atz/` (packages giữ tên cũ: `ingestion`, `filter_runner`, …)
- Config YAML: `config/`
- Docs: `docs/`
- `PYTHONPATH` trỏ `src/atz` (Dockerfile + pytest)

## Quy tắc agent

Xem `.cursor/rules/` và `AGENTS.md`: kế hoạch → xác nhận → mới sửa; không force push; tín hiệu `pos_*` chỉ chat riêng.
