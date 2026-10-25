# Task T-iboard-ohlcv-eod — Seed OHLCV iBoard (EOD / ngoài giờ)

**Owner:** ag2  
**Status:** Done (chờ master_ack)  
**Phạm vi:** dev.atz.vn

## Mục tiêu

Có lệnh chạy trên **host VPS** (không trong container API — mount `data/ohlcv` read-only) để nạp/cập nhật CSV cho rổ `board_universe`, giúp `POST /api/iboard/daily-signals` có `scanned>0`.

## File được sửa

- `backend/ohlcv_seed.py`
- `tests/test_ohlcv_seed.py`
- `docs/HANDOFF_NEXT_CHAT.md` (runbook Ops)

## DoD

- [x] `python -m backend.ohlcv_seed --dry-run` liệt kê universe
- [x] Runbook HANDOFF (venv, seed, restart api, curl verify)
- [x] pytest Pass — `python3 -m pytest tests/test_ohlcv_seed.py -q` (6)

## Ngoài phạm vi

- Prod Streamlit, cron systemd, secrets trong repo.
- Filter `foreign` (cần thêm `data/flow` — không thuộc seed OHLCV).

## Báo

Cập nhật 5 dòng Last executor trên `docs/agents/NOW.md`.
