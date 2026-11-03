# Task T-option-b-rt-quant — Real-time Quant Streaming

**Owner:** ag2  
**Status:** Deploy + smoke desk-dev OK (2026-11-03)  
**Phạm vi:** `backend/engine/stream_*.py`, `backend/ws_alerts.py`, `backend/main.py`, `config/stream_alerts.yaml`, `tests/test_stream_alerts.py`

## Mục tiêu

Redis tick → vectorized RSI/MA/volume → WS `/ws/stream/alerts` (không chặn event loop).

## DoD

- [x] `QuantStreamListener` + `evaluate_rings` (pandas batch)
- [x] WS contract JSON alert
- [x] pytest Pass
- [x] Smoke desk-dev: mock tick (container `/app`) + WS `/ws/stream/alerts` → `RSI_OVERSOLD` PASS

## Smoke (VPS)

```bash
# Deploy
cd /opt/atz-desk && ./scripts/deploy-vps.sh dev-local
docker compose -f docker-compose.dev.yml up -d --force-recreate api

# Mock (trong container api — PYTHONPATH /app)
docker cp scripts/mock_tick_generator.py atz-desk-api-dev:/tmp/mock_tick_generator.py
docker exec -d atz-desk-api-dev sh -c 'cd /app && python /tmp/mock_tick_generator.py --redis-url redis://redis:6379/0 --seed-trend down'

# Hoặc từ host nếu đã pip install redis:
REDIS_URL=redis://127.0.0.1:6380/0 python3 scripts/mock_tick_generator.py
```

WS: `wss://dev.atz.vn/ws/stream/alerts` (hoặc `ws://127.0.0.1:8000/ws/stream/alerts` trên VPS).

## Ngoài phạm vi

- FE toast UI đầy đủ; tắt Streamlit; đổi nginx
