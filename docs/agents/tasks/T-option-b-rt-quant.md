# Task T-option-b-rt-quant — Real-time Quant Streaming

**Owner:** ag2  
**Status:** Code ready — chờ commit/deploy smoke  
**Phạm vi:** `backend/engine/stream_*.py`, `backend/ws_alerts.py`, `backend/main.py`, `config/stream_alerts.yaml`, `tests/test_stream_alerts.py`

## Mục tiêu

Redis tick → vectorized RSI/MA/volume → WS `/ws/stream/alerts` (không chặn event loop).

## DoD

- [x] `QuantStreamListener` + `evaluate_rings` (pandas batch)
- [x] WS contract JSON alert
- [x] pytest Pass
- [ ] Smoke desk-dev: WS alerts nhận tin (khi có tick)

## Ngoài phạm vi

- FE toast UI đầy đủ; tắt Streamlit; đổi nginx
