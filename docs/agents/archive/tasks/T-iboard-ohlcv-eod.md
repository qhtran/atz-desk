# Task T-iboard-ohlcv-eod — Seed OHLCV iBoard (EOD / ngoài giờ)

**Owner:** ag2  
**Status:** ack (2026-10-25) · commit `7ae3da5`  
**Phạm vi:** dev.atz.vn

## Mục tiêu

Có lệnh seed/cập nhật CSV `data/ohlcv` cho rổ `board_universe`, giúp `POST /api/iboard/daily-signals` có `scanned>0` ngoài giờ.

## File được sửa

- `backend/ohlcv_seed.py`
- `scripts/seed-iboard-ohlcv.sh`
- `tests/test_ohlcv_seed.py`
- `scripts/check-dev.sh`
- `docs/HANDOFF_NEXT_CHAT.md`

## DoD

- [x] CLI + script VPS (`vnstocks` container)
- [x] pytest Pass (6)
- [x] Verify VPS: 80 mã seed; daily-signals OK

## Báo executor

Seed VPS 80 mã (78 ok); VN30 rsi matched=3; HOSE advisor matched=45.
