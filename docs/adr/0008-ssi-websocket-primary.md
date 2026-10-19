# ADR 0008 — SSI Market WebSocket primary (REST backup)

- **Status:** Accepted (human 2026-10-20; exe2 implement Phase 1)
- **Context:** UX giật khi UI fragment poll; REST poll chậm hơn push. SSI Developer Portal cung cấp Market WebSocket (`wss://stream.ssi.com.vn`, channel `DATA`) **không cần OTP**. Human chốt WebSocket-first; REST giữ backup. Chi tiết: `docs/REFRESH_1_2S_STRATEGY.md` §5.

## Quyết định

1. **Primary:** service `atz-ssi-stream` (`python -m ingestion.ssi_stream`) subscribe Market DATA → ghi Redis cùng key hiện có (`idx:quote:{SYM}`, `spark:{SYM}` khi có tick phút).
2. **Backup:** `atz-index` (REST SSI `indexSummary`/`ohlc` + Vietcap futures) chạy khi stream **không healthy** (health key cũ / im lặng / disconnect kéo dài). Khi stream healthy, index-feed **không** ghi đè spot index bằng SSI REST (tránh hai writer).
3. **UI / filter không đổi hợp đồng Redis** — chỉ `source` có thể là `SSI_WS` vs `SSI` / `VIETCAP`.
4. **Phase 1 scope:** chỉ số spot (VNINDEX, VN30, HNXINDEX, UPCOMINDEX). Equity full board vẫn KBS batch (`atz-ingestion`) đến Phase 2+.
5. **Secrets:** chỉ `SSI_CONSUMER_ID` / `SSI_CONSUMER_SECRET` trong `.env` (auth REST lấy token cho WS). Không commit token.

## Hệ quả

- Thêm container `atz-ssi-stream` trong `docker-compose.yml`.
- Config `config/ssi_stream.yaml`; index.yaml thêm khối `ssi_stream_backup`.
- Ops: xem `ssi_stream:health` + log `DBG-*-SSI-STREAM-*`. Mất WS → mode backup REST tự bật trên index-feed.

## References

- `docs/REFRESH_1_2S_STRATEGY.md` §5
- https://developers.ssi.com.vn/docs/api-reference/connectWebSocket
- https://developers.ssi.com.vn/docs/tutorials/websocket-data
