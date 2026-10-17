# ADR 0007 — Cổng deploy Exe1 (user_confirmed_infra)

- **Status:** Proposed (Master Architect draft, 2026-10-17)
- **Context:** Multi-agent: Master không SSH production; Exe1 (executor-1) triển khai theo task `Doing` trên PROGRESS.md. Rủi ro mất SSH nếu đụng nginx stream / sshd.

## Quyết định

1. Mọi thay đổi production (Docker rebuild/recreate, Authentik, nginx HTTP site) cần `user_confirmed_infra: yes` trên PROGRESS + owner Exe1 (hoặc human) rõ ràng.
2. Master Architect: chỉ cập nhật bus PROGRESS (authorize / ack); **không** SSH VPS.
3. Deploy UI sau ship code: task riêng (vd. T-160, T-161); scope mặc định `vnstocks` only trừ human chọn ALL.
4. DoD deploy: `git pull` đạt commit tối thiểu; `docker compose build` + `up -d --no-deps --force-recreate <svc>`; `atz-check-upstream` PASS; `_stcore/health` 200 (VPS); không đụng volumes/workers ngoài scope.
5. Master ack: đối chiếu report Exe1 + (tuỳ) public forward-auth 302; ghi Master ack trên PROGRESS; commit+push bus.

## Hệ quả

- Exe1 đọc §6/§7 trước mỗi turn; một `Doing` tại một thời điểm.
- Cấm force-push; cấm commit secrets; cấm OIDC client Streamlit (ADR 0006).

## References

- PROGRESS T-130 / T-160 / T-161
- docs/infrastructure/VPS_NETWORK.md
- ADR 0003, 0006
