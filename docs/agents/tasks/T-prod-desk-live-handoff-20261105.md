# Task T-prod-desk-live-handoff-20261105 — PROD Desk live status (handoff)

**Owner:** ag2 (VPS) — standby  
**Status:** Note / idle (không mở Doing code)  
**Phạm vi:** `/opt/atz-desk` · `docker-compose.prod-desk.yml` · **KHÔNG** đụng `/opt/vnstocks`  
**Nhận:** 2026-11-05 ~00:00 Asia/Saigon (Mac → VPSCode)

## Git tip

| Ref | SHA | Ghi chú |
|-----|-----|---------|
| Journal (main) | `2d51f2b` | `docs/TECH_JOURNAL.md` |
| Code live | `e742ae3` | Master Catalog + Top 240 + on-demand SSI |

**Ship:** Master Catalog + Top 240 core + snapshot fallback + on-demand SSI + TECH_JOURNAL.

## PROD trạng thái (đã verify VPS 2026-11-05)

| Service | Status |
|---------|--------|
| `atz-desk-api` | `:8001` healthy |
| `atz-redis-desk-prod` | healthy |
| `atz-ssi-worker` | Up (profile `live`) — force-recreate ~23:59 |

**SSI CONNECT**
- DATA topics ~**1222**
- X-Quote / X-Trade **242**
- source=`ssi`

**Smoke DBC** `GET /api/quotes/snapshot?symbols=DBC`
- last **15750** · **+3.62%**
- `snap_source=priceboard` · `in_core=true`

## Ops live (không full redeploy trừ khi cần)

```bash
cd /opt/atz-desk
docker compose -f docker-compose.prod-desk.yml --profile live up -d --force-recreate --no-deps ssi-worker
# deploy-prod-desk.sh mặc định KHÔNG bật --profile live
```

## Verify

```bash
curl -fsS http://127.0.0.1:8001/healthz
docker logs atz-ssi-worker --tail 40 | grep SSI-LIVE
curl -fsS 'http://127.0.0.1:8001/api/quotes/snapshot?symbols=DBC'
```

## Next (chỉ khi user bảo)

P1 backlog journal:
- EOD liquidity rank (thay curated ladder)
- Unsubscribe khi xóa mã khỏi mọi watchlist
- Portfolio add-symbol → watch

## Ngoài phạm vi

- Không force push
- Không sửa nginx / Authentik trừ khi yêu cầu rõ
- Không full redeploy trừ khi user yêu cầu
