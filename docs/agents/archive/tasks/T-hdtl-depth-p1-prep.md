# Task T-hdtl-depth-p1-prep — HĐTL depth UX (P1 prep)

**Owner:** ag2  
**Status:** ack (2026-10-25) · commit `6fe7f21`  
**Phạm vi:** dev.atz.vn

## Mục tiêu

Chuẩn bị pipeline depth thật cho VN30F1M/F2M trước khi verify giờ mở cửa.

## Ship

- `tick_kind_for_symbol` — HĐTL parse như dòng cổ phiếu (depth 3 cấp)
- `tick_has_payload` — vẫn đẩy tick khi chỉ có dư mua/bán
- FE `enrichDepth` — đã có bid/ask từ WS thì không điền số giả
- Deploy dev VPS verify: SSI connect OK; ngoài giờ chưa có sổ lệnh thật

## DoD

- [x] pytest Pass (21+)
- [x] dev.atz.vn tab VN30F1M OK

## Chưa (task khác / phiên mở)

- Map field SSI + tắt hẳn số giả khi pass checklist P1
