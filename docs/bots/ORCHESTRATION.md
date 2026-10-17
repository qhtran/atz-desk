# Điều phối đa-bot (Cursor = Orchestrator)

## Vai trò

Roster đầy đủ (Active + Planned): **[`BOTS_ROSTER.md`](BOTS_ROSTER.md)**

| Vai trò | Ai | Việc | Kênh |
|--------|-----|------|------|
| **Orchestrator** | Cursor | Brief, poll git, chốt hướng | Chat + git |
| **Coder / Ops** | **VPSBot** | Code + deploy VPS; brief `inbox/` | `docs/bots/vpsbot/` + SSH:443 |
| **Auditor (read-only)** | **AuditorBot** | So sánh atz vs FireAnt UI/UX / kiến trúc; không sửa | `docs/auditorbot/` |
| **Sec / config** | **SecConfBot** (planned) | Kiểm tra bảo mật & cấu hình sau đổi VPS | `docs/bots/secconfbot/` |
| **Screening** | **Stock Screening Agent** (planned) | CANSLIM, ngành, mẫu hình, dòng tiền | `docs/bots/screening/` |
| **News** | **DailyStockNews** (planned) | Tóm tắt tin + biến động sáng/tối | `docs/bots/dailystocknews/` |
| **Yuanta** | **YSradar Portfolio Agent** (planned) | Đọc/phân tích Portfolio & bảng giá YSradar | `docs/bots/ysradar/` |
| **Chủ repo** | Bạn | Quyết định lớn, bật bot mới | Chat + GitHub |

**Giả định:** bot Active `git pull`/`push` cùng remote.  

**Hướng dẫn:** [`HOW_TO_BAN.md`](HOW_TO_BAN.md) · [`ROLES_ARCHITECT.md`](ROLES_ARCHITECT.md) · [`OVERNIGHT_QUEUE.md`](OVERNIGHT_QUEUE.md) · [`ACCEPTANCE_TESTS.md`](ACCEPTANCE_TESTS.md)

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
