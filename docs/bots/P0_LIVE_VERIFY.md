# P0 — Verify tick live (dev.atz.vn)

**Branch:** `feature/priceboard-debug-trace`  
**URL:** https://dev.atz.vn  
**PR:** `feature/priceboard-debug-trace` → `feature/realtime-fastapi` (#4)

---

## Off-hours snapshot (2026-10-25 ~01:53 ICT)

| Check | Kết quả |
|-------|---------|
| `/healthz` | **200** |
| VPS git HEAD | `122b243` (P1 prep + worker restart) |
| Stack `atz_priceboard` | api **healthy**, ssi-worker running |
| Worker connect | `DBG-…-PB-SSI-LIVE-CONNECT` + `SUBSCRIBED` @ 2026-10-25 01:49 ICT |
| Tick live / volume gate / flash | **Chưa verify** — ngoài phiên GD; không giả tick |
| P1 §4 field map | **TBD** — capture khi phiên mở |

---

## Trong phiên GD (~09:00–15:00 ICT)

### Browser

1. Login Authentik → mở iBoard.
2. Conn dot **connected** · một WS tới `/ws/priceboard`.
3. Index cards: spark + ref/high/low dashed · last đổi (nếu SSI gửi indexsummary).
4. VN30 row: `source=SSI_WS` trong tick (DevTools WS frame) · volume ≥ `min_volume` (500000) hoặc mã bị remove.
5. Flash ô giá khi `last` đổi.
6. (Tuỳ chọn) `?fake_depth=0` — cột bid/ask trống cho tới khi có X-Quote thật.

### VPS worker

```bash
ssh -o BatchMode=yes root@112.213.88.230 \
  'cd /opt/vnstocks && docker compose -f docker-compose.dev.yml logs -f --tail=100 ssi-worker' \
  | grep -E 'PB-SSI-LIVE|ERR-PB'
```

Pass: `CONNECT` / `SUBSCRIBED` · không lặp `ERR-PB-003` auth · tick publish (volume gate).

### Capture → P1 §4

- Rate-limited `ERR-PB-006` + `SSI-PARSE-MISS` → `body_keys` gợi ý alias cần map.
- Hoặc ghi 5–10 envelope **redacted** local `docs/refs/` (không commit secret).
- Điền bảng [PRICEBOARD_P1_DEPTH_NN.md §4](../specs/PRICEBOARD_P1_DEPTH_NN.md) → user chọn `2a`/`2b` trước code depth.

---

## Sau deploy code Python

```bash
ssh -o BatchMode=yes root@112.213.88.230 \
  'cd /opt/vnstocks && git pull --ff-only origin feature/priceboard-debug-trace && \
   docker compose -f docker-compose.dev.yml restart api ssi-worker'
```

FE (`frontend/index.html`) mount — **không** cần restart sau pull.
