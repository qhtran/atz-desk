# PROTOCOL — VPSbot

## Phạm vi

- Sửa code trong repo `vnstocks` / `quanlychungkhoan` theo brief.
- Chạy test liên quan module; báo Pass/Fail.
- Commit nhỏ, push; merge `main` nếu brief cho phép.
- Deploy VPS: `/opt/vnstocks`, `docker compose build` + `up -d --no-deps` đúng service (thường `vnstocks`, đôi khi `ingestion`).
- Đọc `AGENTS.md`, `docs/architecture.md`, `docs/troubleshooting.md` trước khi sửa lớn.

## Không làm

- Force push; sửa `.env` / secret; nginx / Authentik / SSH / firewall trừ brief **P0 + user xác nhận**.
- Thêm tính năng lớn ngoài brief.
- Broadcast `pos_*` ra channel.

## Git / file (bắt buộc push)

VPSbot **có quyền git push** cùng remote. Mọi brief/outbox đi qua GitHub — không copy tay.

| Path | Ai ghi + push |
|------|----------------|
| `docs/bots/vpsbot/inbox/YYYYMMDD-HHMM-<topic>.md` | Orchestrator (Cursor) hoặc user |
| `docs/bots/vpsbot/outbox/YYYYMMDD-HHMM-<topic>-DONE.md` (hoặc `-FAIL.md`) | VPSbot |
| code / tests / config theo brief | VPSbot |

Trước khi làm: `git pull --ff-only origin main` (hoặc rebase branch brief).  
Xong: push branch + outbox; merge `main` chỉ khi brief `merge_main: yes`.

Tên brief và outbox **cùng stem topic** để Cursor ghép cặp.

## Commit message

- Code: theo style repo (tiếng Anh, why-focused).
- Docs resolution: `docs(vpsbot): resolve <topic>`.

## Definition of Done (mặc định)

- [ ] Diff đúng phạm vi brief  
- [ ] Test module Pass (hoặc ghi rõ skip vì sao)  
- [ ] Đã push (và merge main nếu brief yêu cầu)  
- [ ] Deploy VPS nếu brief `deploy: yes`  
- [ ] Outbox có Summary + lệnh đã chạy + HEAD commit  
