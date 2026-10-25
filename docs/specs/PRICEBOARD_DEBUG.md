# Priceboard debug & trace (dev.atz.vn)

**Phạm vi:** stack FastAPI + worker trong [`backend/`](../../backend/) · `docker-compose.dev.yml` · **không** áp dụng Streamlit prod `src/atz`.

## 1. Debug label

```
[DBG-YYYYMMDD-HHMM-PB-{ACTION}]
```

Ví dụ: `[DBG-20261025-0143-PB-API-START]`, `[DBG-20261025-0143-PB-REDIS-LISTENER] ERR-PB-001 {...}`

## 2. Error code

```
ERR-PB-{NNN}
```

Registry trong code: [`backend/observability/codes.py`](../../backend/observability/codes.py).

| Mã | Mô tả | Gợi ý xử lý |
|----|--------|-------------|
| ERR-PB-001 | Redis unreachable / ping fail | `atz-redis-dev`, `REDIS_URL`, network compose |
| ERR-PB-002 | Redis pub/sub hoặc HSET lỗi | Redis memory, connection reset |
| ERR-PB-003 | YAML `config/priceboard.yaml` lỗi | Sửa YAML / quyền mount volume |
| ERR-PB-004 | SSI auth / token | `.env` `SSI_CONSUMER_*`, IP whitelist SSI |
| ERR-PB-005 | SSI WS session / mock reconnect | Log trước đó + `exc_message` |
| ERR-PB-006 | Parse tick SSI (dự phòng) | Cập nhật `tick_contract.parse_ssi_envelope` |
| ERR-PB-007 | WebSocket stale / handler | Client disconnect, proxy timeout |
| ERR-PB-008 | Screener rule/request invalid | API trả `error_code` + sửa rule |
| ERR-PB-009 | Fallback mock (thiếu SSI cred) | Bổ sung secret hoặc `PRICEBOARD_SOURCE=mock` |

## 3. Structured JSON

Mọi dòng log kèm JSON (stdout → `docker logs`):

- `debug_label`, `error_code`, `module` (`PB`), `message`, `ts`
- Khi có lỗi: **`origin`**: `{ file, line, function, qualname }`
- Khi truyền exception: `exc_type`, `exc_message` (cắt 500 ký tự)
- Tuỳ chọn: `LOG_TRACE_STACK=1` → thêm `stack_tail` (3 frame)

## 4. Trace workflow

1. Lấy `ERR-PB-*` từ log hoặc response API screener.
2. Mở `origin.file` + dòng `origin.line` trong repo (nhánh priceboard).
3. Grep cùng `debug_label` hoặc `symbol` / `channel` trong context JSON.
4. Đối chiếu bảng mã ở trên.

```bash
docker compose -f docker-compose.dev.yml logs api 2>&1 | grep ERR-PB
docker compose -f docker-compose.dev.yml logs ssi-worker 2>&1 | grep DBG- | tail -20
```

## 5. Debug UI overlay (Inspect)

- Bật: `config/debug_overlay.yaml` → `surfaces.priceboard.enabled` (hoặc env `PB_DEBUG_UI=1`).
- Trên trang: **⌘⇧D / Ctrl⇧D** · hover highlight · click pin → **Copy JSON** (`pb-ui:*` + hints / `ERR-PB-*` từ [`frontend/ui_catalog.json`](../../frontend/ui_catalog.json)).
- Tắt nhanh: `PB_DEBUG_UI=0` hoặc Esc.
- Checklist: [`docs/bots/P0_LIVE_VERIFY.md`](../bots/P0_LIVE_VERIFY.md) mục Inspect.

## 6. Ví dụ

```text
[DBG-20261025-0930-PB-HEALTH-REDIS] ERR-PB-001 {"ts":"...","debug_label":"DBG-20261025-0930-PB-HEALTH-REDIS","error_code":"ERR-PB-001","module":"PB","message":"redis ping failed","origin":{"file":"/app/backend/main.py","line":54,"function":"healthz","qualname":"healthz"},"exc_type":"ConnectionError","exc_message":"..."}
```

## 7. Liên kết

- Kiến trúc §8.1: [`docs/architecture.md`](../architecture.md)
- User Manual Streamlit (prod khác stack): [`docs/troubleshooting.md`](../troubleshooting.md) — priceboard dev dùng tài liệu này.
