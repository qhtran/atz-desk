# Điều phối đa-bot (Cursor = Orchestrator)

## Vai trò

| Vai trò | Ai | Việc | Kênh |
|--------|-----|------|------|
| **Orchestrator** | Cursor (Composer) trong chat này | Hiểu mục tiêu user → chia việc → đọc kết quả → chốt ưu tiên `1a/1b…` → (tuỳ chọn) review diff | Chat Cursor + git |
| **Auditor** | AuditorBot (Grok + computer use) | Survey **atz.vn** / **fireant.vn**, báo cáo lệch UI/UX | `docs/auditorbot/inbox/` |
| **Coder / Ops / Infra** | VPSbot | Code, test, commit; **Docker/Compose**, deploy `/opt/vnstocks`, Redis/SQLite, nginx & server setup (+ `user_confirmed_infra` nếu rủi ro) | GitHub inbox/outbox + **SSH:443 → VPS** |
| **Chủ repo** | Bạn | Quyết định lớn, auth bot lần đầu, chuyển prompt khởi động | Chat + GitHub |

**Giả định nền (đã chốt):** **mọi bot đều `git pull` / `git push` được** cùng remote GitHub. Không copy tay file giữa máy trừ khi git lỗi.

**Hướng dẫn chủ repo:** [`HOW_TO_BAN.md`](HOW_TO_BAN.md)  
**Phân vai Wave hiện tại:** [`ROLES_ARCHITECT.md`](ROLES_ARCHITECT.md) — Cursor = kiến trúc sư; VPSbot = code; AuditorBot = test/survey.

**Nguyên tắc tiết kiệm token Cursor:** survey dài + code/deploy lặp → giao bot. Cursor: brief ngắn → push hộp việc → sau đó `pull` đọc kết quả → hỏi user.

---

## Hộp việc (bot poll chỗ này)

| Bot | Việc mới nằm ở | Kết quả bot push vào |
|-----|----------------|----------------------|
| AuditorBot | `docs/auditorbot/tasks/` | `docs/auditorbot/inbox/` (báo cáo) |
| VPSbot | `docs/bots/vpsbot/inbox/` | `docs/bots/vpsbot/outbox/` (+ code) |

### Rule poll (cả hai bot — ghi trong PROTOCOL + PROMPT)

1. Mỗi **~5 phút** (và ngay khi xong 1 việc): `git pull --ff-only origin main`.
2. Tìm **1** file việc chưa làm xong (chưa có kết quả cùng stem).
3. Làm đúng file đó → push kết quả.
4. Không có việc → ngủ đến chu kỳ sau. **Không tắt** vòng poll khi phiên còn mở.
5. Lỗi git/SSH → ghi FAIL (nếu được) + báo user 1 câu.

---

## Luồng chuẩn (toàn bộ qua git)

```
User yêu cầu
    ↓
Cursor [DBG] plan + lựa chọn số
    ↓  git commit+push vào tasks/ hoặc vpsbot/inbox/
┌─────────────────┬──────────────────┐
│ AuditorBot      │ VPSbot           │
│ poll → survey   │ poll → code/SSH  │
│ push inbox/     │ push code+outbox │
└────────┬────────┴────────┬─────────┘
         ↓  git pull
Cursor đọc → tóm tắt user → Resolution / brief tiếp
```

1. Cursor (hoặc user) **commit + push** file việc vào đúng hộp (bảng trên).
2. Bot đang chạy PROMPT **tự poll** — không cần gõ «đi làm» mỗi lần.
3. Bot **push** kết quả.
4. User bảo Cursor: *«pull, đọc auditor inbox / vps outbox»*.
5. Cursor cập nhật Resolution; chuyển báo cáo auditor `inbox/` → `reports/` khi xong.

---

## Khi nào Cursor tự làm (không giao bot)

- Sửa rất nhỏ / nóng (1 file, bug chặn production) mà VPSbot chưa sẵn.
- Verify 1 màn sau deploy (browser Cursor **ngắn**).
- Viết/chỉnh protocol, brief, template.
- Rủi ro: secret, nginx, SSH, firewall → **dừng, hỏi user**; nếu giao VPSbot thì brief phải có `user_confirmed_infra: yes`.

---

## Thư mục

```
docs/auditorbot/
  tasks/             # hộp việc survey (Orchestrator push)
  inbox/             # báo cáo AuditorBot
  reports/
docs/bots/
  HOW_TO_BAN.md      # hướng dẫn chủ repo
  ORCHESTRATION.md
  vpsbot/
    inbox/           # hộp việc code/deploy
    outbox/          # DONE / FAIL
```

---

## Quy tắc giao tiếp Cursor (giữ nguyên)

- Mọi phản hồi bắt đầu `[DBG] intent=… | modules=… | files=… | conf=…`
- Hỏi user bằng lựa chọn đánh số `1a` / `1b`… (quyết định sản phẩm) — **không** hỏi user chạy cmd trong repo
- Orchestrator **tự** git pull/push / thao tác file trong project (xem `ROLES_ARCHITECT.md`)
- Karpathy: kế hoạch ngắn trước khi sửa code lớn; không force-push; không xóa phá dự án; không đụng file ngoài project
