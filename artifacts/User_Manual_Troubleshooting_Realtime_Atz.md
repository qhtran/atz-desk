# User Manual & Troubleshooting Guide - Hệ thống Realtime atz.vn

**Phiên bản**: 1.0  
**Ngày**: 2026-10-16  
**Mục đích**: Tài liệu vận hành và xử lý sự cố. Mọi lỗi đều có mã, mọi log đều có debug label để software engineer có thể trace và fix bug nhanh chóng.

---

## 1. Tổng quan hệ thống

Hệ thống near-realtime tracking cổ phiếu Việt Nam. Không thực hiện giao dịch trực tiếp.

**Các module chính**:
1. Ingestion Service (KBS + VCI)
2. Streaming Filter Runner
3. Alert Dispatcher
4. Live Position Monitor
5. UI Streamlit (Realtime)
6. Order Action Helper

**Hạ tầng**: Docker Compose trên VPS, Redis (cache + stream), SQLite, Streamlit + Authentik.

---

## 2. Nguyên tắc Traceability (Bắt buộc)

### 2.1 Debug Label
Mọi log phải có debug label theo format:

```
[DBG-YYYYMMDD-HHMM-MODULE-ACTION]
```

Ví dụ:
- `[DBG-20261016-1026-INGEST-FETCH]`
- `[DBG-20261016-1026-FILTER-EVAL]`
- `[DBG-20261016-1026-ALERT-SEND]`
- `[DBG-20261016-1026-POS-CALC]`

### 2.2 Error Code
Mọi exception hoặc lỗi nghiệp vụ phải có **Error Code** dạng:

```
ERR-<MODULE>-<NUMBER>
```

Ví dụ: `ERR-INGEST-001`, `ERR-FILTER-003`, `ERR-ALERT-002`

### 2.3 Structured Log
Log nên chứa các trường tối thiểu:
- `debug_label`
- `error_code` (nếu có lỗi)
- `module`
- `symbol` (nếu liên quan)
- `user_id` (nếu liên quan)
- `latency_ms`
- `message`

---

## 3. Danh mục Error Code

### Ingestion Service
| Error Code       | Mô tả                              | Nguyên nhân thường gặp                  | Cách xử lý                                      |
|------------------|------------------------------------|-----------------------------------------|-------------------------------------------------|
| ERR-INGEST-001   | Rate limit exceeded                | Vượt 380 req/phút                       | Kiểm tra Rate Limiter, tăng interval            |
| ERR-INGEST-002   | Circuit Breaker Open (KBS)         | KBS lỗi liên tục                        | Chờ recovery hoặc kiểm tra nguồn KBS            |
| ERR-INGEST-003   | Circuit Breaker Open (VCI)         | VCI lỗi liên tục                        | Tương tự trên                                   |
| ERR-INGEST-004   | Both sources down                  | Degradation mode                        | Kiểm tra network, vnstock key, chờ nguồn hồi    |
| ERR-INGEST-005   | Normalize failed                   | Schema không khớp                      | Kiểm tra raw data từ nguồn                      |
| ERR-INGEST-006   | Redis write failed                 | Redis down hoặc full                    | Kiểm tra Redis container                        |
| ERR-INGEST-007   | Timeout on request                 | Nguồn phản hồi chậm                     | Tăng timeout hoặc kiểm tra mạng                 |

### Filter Runner
| Error Code       | Mô tả                              | Cách xử lý                                      |
|------------------|------------------------------------|-------------------------------------------------|
| ERR-FILTER-001   | Filter evaluate timeout            | Kiểm tra filter có vòng lặp vô hạn không        |
| ERR-FILTER-002   | Filter exception isolated          | Xem log chi tiết của filter đó                  |
| ERR-FILTER-003   | Filter temporarily disabled        | Circuit của filter đã mở                        |
| ERR-FILTER-004   | Dedup check failed                 | Kiểm tra Redis                                  |

### Alert Dispatcher
| Error Code       | Mô tả                              | Cách xử lý                                      |
|------------------|------------------------------------|-------------------------------------------------|
| ERR-ALERT-001    | Telegram send failed               | Kiểm tra bot token (.env.alert), network, bot còn là admin channel |
| ERR-ALERT-002    | Email (Brevo) failed               | Brevo HTTP API lỗi (401 key sai/IP chưa whitelist, 400 sender chưa verify); kiểm tra BREVO_API_KEY trong .env.alert |
| ERR-ALERT-003    | Channel circuit open               | 5 lỗi/300s -> tạm dừng 300s rồi thử lại; user fallback sang email (nếu bật) |
| ERR-ALERT-004    | User rate limit hit                | >10/5min hoặc >30/giờ (user hoặc channel broadcast); vẫn ghi in-app |
| ERR-ALERT-005    | Preference not found               | User chưa có telegram_chat_id/email (log tối đa 1 lần/user/giờ); chỉ in-app + broadcast |

**Alert Dispatcher - hành vi (Module 3)**: container `atz-alert`, config `config/alert_dispatcher.yaml`, secret `.env.alert` (chmod 600, không commit).
- Mỗi signal: dedup theo signal_id (24h) -> ghi `signal_history` (unique user+mã+filter+ngày) -> in-app (`inapp:{user_id}` Redis) -> channel broadcast Telegram (`-1003736327598`, gộp cùng mã+filter+chiều 10 phút, rate limit 10/5min 30/h) -> kênh riêng user (Telegram ưu tiên, fallback Email).
- Signal riêng tư: `filter_name` bắt đầu bằng `channels.telegram.private_filter_prefixes` (mặc định `pos_`, vd pos_stop_loss/pos_take_profit/pos_volatility của Module 4) KHÔNG BAO GIỜ gửi channel broadcast; chỉ chat Telegram riêng của user, fallback email, in-app. Log `ALERT-ROUTE` "private signal, broadcast skipped".
- Quiet hours: `cai_dat_chung.quiet_hours = {"start":"22:00","end":"07:00"}` (giờ +07:00); trong giờ yên lặng chỉ ghi in-app.
- Email: Brevo HTTP API `POST https://api.brevo.com/v3/smtp/email` (header api-key), sender mặc định `mail@atz.vn`, user cần `email_nhan_thong_bao` + `cai_dat_chung.email_bat=true`; tắt bằng `channels.email.enabled: false`.
- Delivery log: bảng SQLite `alert_deliveries` (status sent/failed/skipped + error_code + provider_message_id = Telegram message_id / Brevo messageId).
- Lệnh: `docker exec atz-alert python -m alert_dispatcher.health`; `docker logs atz-alert --tail 100`.

### Position Monitor
| Error Code       | Mô tả                              | Cách xử lý                                      |
|------------------|------------------------------------|-------------------------------------------------|
| ERR-POS-001      | Price stale                        | Quote > 120s, quote.stale=true, ingestion degraded hoặc mất heartbeat. Vị thế bị đánh dấu stale, KHÔNG cảnh báo SL/TP/biến động (log tối đa 1 lần/user+mã/5 phút). Kiểm tra `atz-ingestion` |
| ERR-POS-002      | P&L calculation error              | entry_price/quantity <= 0 hoặc giá không phải số. Kiểm tra dòng trong bảng `positions` |

**Position Monitor - hành vi (Module 4)**: container `atz-position`, config `config/position_monitor.yaml`, không cần secret (chỉ mạng `realtime`).
- Vị thế: bảng SQLite `positions` (data/signals.db, migration chỉ CREATE IF NOT EXISTS). Giá theo **VND** (cùng quote); chỉ LONG. Tab Danh mục cũ (`data/positions.csv`, nghìn đồng) không liên quan.
- Giá: consumer group `position-monitor` trên `stream:quotes` + sweep 15s đọc `quote:{symbol}` (timeout 2s). P&L = (giá - giá vốn) x KL; ghi Redis hash `pos:live:{user_id}` (field = position id) cho UI.
- Cảnh báo -> `stream:signals` theo Signal contract, nên đi qua Module 3 như signal thường (rate limit, quiet hours, channel `atz_alert` + chat riêng):
  - `pos_stop_loss` (SELL) khi giá <= stop_loss; `pos_take_profit` (SELL) khi giá >= take_profit. Mỗi mức bắn **1 lần** / vị thế (cột `sl_hit_at`/`tp_hit_at`, bền qua restart). Bật lại: `cli rearm ID` hoặc đổi mức bằng `cli set`.
  - `pos_volatility` (BUY nếu tăng, SELL nếu giảm) khi |biến động| >= 3% trong 300s; dedup 30 phút / vị thế / chiều (Redis `pos:vdedup:*`).
  - Lưu ý Module 3: `signal_history` unique theo user+mã+filter+ngày nên cảnh báo lặp cùng ngày vẫn gửi nhưng dùng chung 1 dòng history.
- Lệnh: `docker exec atz-position python -m position_monitor.health`; `docker logs atz-position --tail 100`.
- Nhập vị thế (chưa có UI, Module 5): `docker exec atz-position python -m position_monitor.cli add --user akadmin --symbol FPT --qty 100 --entry 58600 --sl 55000 --tp 65000` (`--unit k` để nhập nghìn đồng); `cli list`, `cli live --user akadmin`, `cli set ID --sl X`, `cli rearm ID`, `cli close ID`.

### Chung
| Error Code       | Mô tả                              | Cách xử lý                                      |
|------------------|------------------------------------|-------------------------------------------------|
| ERR-SYS-001      | Redis connection failed            | Restart Redis container                         |
| ERR-SYS-002      | SQLite locked                      | Kiểm tra concurrent write                       |
| ERR-SYS-003      | Config load failed                 | Kiểm tra file yaml / env                        |

---

## 4. Cách Trace một lỗi

1. **Lấy Error Code** từ log hoặc UI.
2. **Tìm debug label** gần nhất trong log của module tương ứng.
3. **Xem context**:
   - `symbol`, `user_id`, `batch_id`, `signal_id`
   - `latency_ms`, `source`, `circuit_state`
4. **Kiểm tra Health**:
   - Trạng thái Circuit Breaker
   - Redis có dữ liệu không
   - Container có đang chạy không
5. **Đối chiếu bảng Error Code** ở trên để có hướng xử lý ban đầu.
6. **Nếu cần sâu hơn**: xem raw log với cùng `debug_label` hoặc `batch_id`.

### Ví dụ Trace
```
Log: [DBG-20261016-1026-INGEST-FETCH] ERR-INGEST-002 Circuit Open for KBS, switching to VCI
→ Tra ERR-INGEST-002 → KBS đang lỗi liên tục
→ Kiểm tra log trước đó với cùng debug label để xem lỗi gốc của KBS
→ Kiểm tra vnstock key và kết nối mạng
```

---

## 5. Health Check & Monitoring

Mỗi service nên expose hoặc log định kỳ:

- `ingestion_health`: circuit state của KBS/VCI, last successful fetch, rpm hiện tại
- `filter_runner_health`: số signal/phút, số filter bị disable
- `alert_health`: tỷ lệ gửi thành công theo kênh
- `redis_health`: ping + memory

**Lệnh kiểm tra nhanh trên VPS**:
```bash
docker ps
docker logs atz-ingestion --tail 100
docker logs atz-redis --tail 50
```

---

## 6. Cấu hình quan trọng

File cấu hình chính (ví dụ `config/ingestion.yaml`):
- `safety_max_rpm`
- `circuit_breaker.failure_threshold`
- `poll_interval_seconds`
- `batch_size`

Thay đổi config → restart service tương ứng.

---

### 6.1 Rate limit nguồn dữ liệu (đo thực tế 2026-10-16, từ VPS 112.213.88.230)
Probe `[DBG-20261016-0624..0629-INGEST-RATEPROBE]`, trong phiên, ingestion tạm dừng; mỗi nguồn riêng, cùng shape production (`price_board` 30 mã/1 request), bậc 10→240 rpm, 30s/bậc.

| Nguồn | 10 | 20 | 30 | 45 | 60 | 90 | 120 | 180 | 240 rpm | Lỗi |
|---|---|---|---|---|---|---|---|---|---|---|
| KBS p50/p95 ms | 110/307 | 101/191 | 103/169 | 96/118 | 101/131 | 102/129 | 102/130 | 99/129 | 102/146 | 0 |
| VCI p50/p95 ms | 598/1413 | 602/642 | 609/673 | 615/673 | 598/647 | 601/708 | 602/679 | 592/681 | 590/669 | 0 |

- Kết luận: **chưa chạm limit ở trần thử 240 rpm** cho cả KBS và VCI (không 429/403, không lỗi kết nối, latency phẳng). Limit dùng để tính = 240 (giới hạn dưới, không phải limit thật).
- Header rate-limit (X-RateLimit-*, Retry-After): **không quan sát được** — vnstock 5.0.1 gọi HTTP qua native engine, không đi qua `requests`/`http.client` của Python.
- Giới hạn tier (nguồn: tài liệu vnstock; tài khoản đã xác nhận **Golden** qua `vnstock status`): 500–600 request/phút, 36.000/giờ, 150.000/ngày.
- Cấu hình (đã duyệt 2026-10-16): `safety_max_rpm = 350` = 70% × 500 (mức thấp của tier). Một bucket dùng chung cho mọi nguồn. Probe chỉ xác nhận KBS/VCI ổn tới 240 rpm — vùng 240–350 chưa thử trực tiếp.
- `poll_interval_seconds = 3`: 30 mã/batch 50 = 1 request/chu kỳ = ~20 rpm (≈1.200/giờ = 3,3% hạn mức giờ). Mỗi ngày ≈ 6h phiên × 1.200 + 18h × 60 (poll 60s ngoài giờ) ≈ 8.300 request ≈ 5,5% hạn mức 150K/ngày. Xấu nhất (KBS+VCI 3 lần thử mỗi chu kỳ) = 120 rpm ≤ 350.
- Nếu thấy `ERR-INGEST` 429/403 sau khi đổi: tăng `poll_interval_seconds` về 5–8 rồi đo lại. Thêm mã (>50) sẽ tăng request/chu kỳ — tính lại `ceil(n/batch) × 60/interval ≤ safety_max_rpm`.

## 7. Quy trình xử lý sự cố chuẩn

1. Xác định module bị ảnh hưởng (từ Error Code hoặc triệu chứng).
2. Lấy log với debug label liên quan.
3. Đối chiếu Error Code.
4. Kiểm tra dependency (Redis, nguồn dữ liệu, network).
5. Áp dụng hành động sửa (restart, điều chỉnh config, fix code).
6. Xác nhận health check trở lại bình thường.
7. Ghi chú vào log vận hành (nếu có).

---

## 8. Liên hệ & Tài liệu liên quan

- Thiết kế chi tiết: `Kien_Truc_He_Thong_Realtime_Atz.md`
- Log location: volume `./logs` hoặc `docker logs`
- Redis: container `atz-redis`

---

*Tài liệu này phải được cập nhật mỗi khi thêm Error Code mới hoặc thay đổi hành vi resilience.*
