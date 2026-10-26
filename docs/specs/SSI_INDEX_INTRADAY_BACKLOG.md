# Backlog — SSI intraday backfill (index spark)

**Trạng thái:** Phase 2 (sau ship index spark 1m local + Redis).

## Mục tiêu

Bù đoạn sáng thiếu khi worker bật muộn — merge vào `index_intraday_1m` cùng `trading_date`.

## Việc research

1. Đối chiếu [SSI Market Data v3](https://developers.ssi.com.vn) — endpoint chart/intraday index (ngoài `indexSummary` một ngày).
2. Spike: 1 mã `VNINDEX`, 1 ngày, so field timestamp + level với bar 1m SQLite.
3. Nếu pass: `backfill_index_spark(client, symbol, trading_date)` + trigger khi API spark thiếu phút đầu phiên.

## Pass / fail

- **Pass:** insert được ≥100 phút trong phiên từ REST; không trùng lệch >1 phút so với WS.
- **Fail:** ghi rõ endpoint không có → chấp nhận giới hạn worker uptime (plan 1c).
