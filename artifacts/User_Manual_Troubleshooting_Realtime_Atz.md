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
| ERR-ALERT-001    | Telegram send failed               | Kiểm tra bot token, network                     |
| ERR-ALERT-002    | Email (Brevo) failed               | Kiểm tra API key Brevo                          |
| ERR-ALERT-003    | Channel circuit open               | Kênh đang bị tạm dừng                           |
| ERR-ALERT-004    | User rate limit hit                | User nhận quá nhiều alert                       |
| ERR-ALERT-005    | Preference not found               | User chưa cấu hình kênh                         |

### Position Monitor
| Error Code       | Mô tả                              | Cách xử lý                                      |
|------------------|------------------------------------|-------------------------------------------------|
| ERR-POS-001      | Price stale                        | Dữ liệu giá quá cũ                              |
| ERR-POS-002      | P&L calculation error              | Kiểm tra dữ liệu vị thế                         |

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
