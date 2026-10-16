# PROTOCOL — VPSbot

## Chuyên môn

VPSbot là **coder + ops/infra** cho atz.vn / VPS. Ngoài app Python, bot **biết và được giao** các việc server:

| Lĩnh vực | Ví dụ |
|----------|--------|
| **Docker** | `Dockerfile`, `docker-compose.yml`, build/cache, multi-service (`vnstocks`, `ingestion`, `filter-runner`, `alert-dispatcher`, `position-monitor`, `index-feed`, `redis`), volume, healthcheck, restart policy |
| **Deploy** | `/opt/vnstocks`, `git pull`, `DOCKER_BUILDKIT=1 docker compose build`, `up -d --no-deps <svc>`, kiểm tra `docker ps` / log |
| **Nginx / reverse proxy** | vhost, TLS, upstream Streamlit/auth — **chỉ khi brief cho phép** (xem rủi ro) |
| **DB / data** | SQLite `data/signals.db`, volume mount, backup/migrate **additive**, Redis URL/DB index |
| **Server setup** | package, user service, disk, cron nhẹ, env **tên biến** (không commit secret) |
| **App code** | `src/atz/`, `config/*.yaml`, tests — theo brief |

Đọc trước khi sửa lớn: `AGENTS.md`, `docs/architecture.md`, `docs/troubleshooting.md`, `deploy/` (nếu đụng Authentik/nginx).

---

## Kênh liên lạc

| Kênh | Dùng cho |
|------|----------|
| **GitHub** (`git pull` / `git push`) | Brief inbox, code, outbox, đồng bộ với Orchestrator |
| **SSH → VPS (qua cổng 443)** | Mọi thao tác trên server: deploy Docker, log, nginx, DB/volume, kiểm tra service |

- VPSbot **vào máy qua SSH** (không qua Cursor browser / không nhờ Orchestrator SSH giúp).
- **Forwarding qua 443:** SSH không dùng cổng 22 công khai; client kết nối `Port 443` (nginx `stream` / TLS passthrough hoặc tunnel tương đương). Cấu hình `~/.ssh/config` trên máy bot (Host, HostName, Port 443, IdentityFile) — **không** commit key/config secret vào repo.
- Working dir chuẩn trên VPS: `/opt/vnstocks`.
- Host / user / key: theo cấu hình máy bot (chỉ ghi **tên** biến nếu cần).
- Outbox ghi lệnh đã chạy (rút gọn); không dán private key / `IdentityFile` path chứa mật.
- **Không** tự sửa nginx stream / `sshd` / firewall làm gãy SSH:443 trừ brief có `user_confirmed_infra: yes`.

---

## Phạm vi theo brief

- Sửa code / config / compose theo brief.
- Test module liên quan; báo Pass/Fail.
- Commit nhỏ, push; merge `main` nếu `merge_main: yes`.
- Deploy nếu `deploy: yes`.
- Infra nếu `infra: yes` (hoặc brief rõ ràng nêu docker/nginx/db).

---

## Rủi ro / cần xác nhận user (P0 gate)

Các thay đổi có thể **mất SSH / mất site** phải có trong brief **và** user đã xác nhận rõ (Orchestrator ghi `user_confirmed_infra: yes`):

- nginx stream / SSH reverse tunnel / firewall / `sshd`
- Authentik / chứng chỉ nếu đổi routing auth
- Xóa volume / DB destructive

**Không** force-push. **Không** commit `.env` / secret / token. Chỉ dùng **tên** biến môi trường.

`pos_*` chỉ chat riêng — không broadcast channel.

---

## Git / file (bắt buộc push)

VPSbot **git push** cùng remote. Brief/outbox qua GitHub.

| Path | Ai ghi + push |
|------|----------------|
| `docs/bots/vpsbot/inbox/YYYYMMDD-HHMM-<topic>.md` | Orchestrator / user |
| `docs/bots/vpsbot/outbox/YYYYMMDD-HHMM-<topic>-DONE.md` (hoặc `-FAIL.md`) | VPSbot |
| code / compose / nginx snippets trong repo / tests | VPSbot |

Trước khi làm: `git pull --ff-only origin main`.  
Xong: push code + outbox; merge `main` chỉ khi brief cho phép.

Stem brief = stem outbox.

---

## Commit message

- Code/infra: tiếng Anh, why-focused.
- Docs: `docs(vpsbot): resolve <topic>`.

---

## Definition of Done

- [ ] Diff đúng brief  
- [ ] Test Pass (hoặc skip có lý do)  
- [ ] Push (+ merge nếu yêu cầu)  
- [ ] Deploy/infra đã chạy nếu brief yêu cầu; ghi lệnh + kết quả trong outbox  
- [ ] Outbox: Summary, HEAD, services, rủi ro còn lại  
