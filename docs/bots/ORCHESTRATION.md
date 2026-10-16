# Điều phối đa-bot (Cursor = Orchestrator)

## Vai trò

| Vai trò | Ai | Việc | Kênh |
|--------|-----|------|------|
| **Orchestrator** | Cursor (Composer) trong chat này | Hiểu mục tiêu user → chia việc → đọc kết quả → chốt ưu tiên `1a/1b…` → (tuỳ chọn) review diff | Chat Cursor + git |
| **Auditor** | AuditorBot (Grok + computer use) | Survey **atz.vn** / **fireant.vn**, báo cáo lệch UI/UX | `docs/auditorbot/inbox/` |
| **Coder / Ops / Infra** | VPSbot | Code, test, commit; **Docker/Compose**, deploy `/opt/vnstocks`, Redis/SQLite, nginx & server setup theo brief (+ `user_confirmed_infra` nếu rủi ro) | `docs/bots/vpsbot/inbox/` → `outbox/` |
| **Chủ repo** | Bạn | Quyết định lớn, auth bot lần đầu, chuyển prompt khởi động | Chat + GitHub |

**Giả định nền (đã chốt):** **mọi bot đều `git pull` / `git push` được** cùng remote GitHub. Không copy tay file giữa máy trừ khi git lỗi.

**Nguyên tắc tiết kiệm token Cursor:** survey dài + code/deploy lặp → giao bot. Cursor: brief ngắn → push inbox → sau đó `pull` đọc outbox/inbox → hỏi user.

---

## Luồng chuẩn (toàn bộ qua git)

```
User yêu cầu
    ↓
Cursor [DBG] plan + lựa chọn số
    ↓  git commit+push brief
┌─────────────────┬──────────────────┐
│ AuditorBot      │ VPSbot           │
│ pull → survey   │ pull → code      │
│ push inbox/     │ push code+outbox │
└────────┬────────┴────────┬─────────┘
         ↓  git pull
Cursor đọc → tóm tắt user → Resolution / brief tiếp
```

1. Cursor (hoặc user) **commit + push** brief vào inbox đúng bot.
2. User bảo bot ngoài: *«pull main, đọc inbox mới nhất»* (hoặc bot tự poll nếu có).
3. Bot **push** kết quả (báo cáo / code / outbox).
4. User bảo Cursor: *«pull, đọc auditor inbox / vps outbox»*.
5. Cursor cập nhật Resolution; move `inbox/` → `reports/` khi xong (commit+push).

---

## Khi nào Cursor tự làm (không giao bot)

- Sửa rất nhỏ / nóng (1 file, bug chặn production) mà VPSbot chưa sẵn.
- Verify 1 màn sau deploy (browser Cursor **ngắn**).
- Viết/chỉnh protocol, brief, template.
- Rủi ro: secret, nginx, SSH, firewall → **dừng, hỏi user**; nếu giao VPSbot thì brief phải có `user_confirmed_infra: yes`.

---

## Thư mục

```
docs/auditorbot/     # xem README riêng
docs/bots/
  ORCHESTRATION.md   # file này
  vpsbot/
    README.md
    PROTOCOL.md
    TASK_TEMPLATE.md
    PROMPT_FOR_VPSBOT.md
    inbox/           # brief từ Orchestrator / user
    outbox/          # VPSbot báo cáo DONE / FAIL
```

---

## Quy tắc giao tiếp Cursor (giữ nguyên)

- Mọi phản hồi bắt đầu `[DBG] intent=… | modules=… | files=… | conf=…`
- Hỏi user bằng lựa chọn đánh số `1a` / `1b`…
- Karpathy: kế hoạch ngắn trước khi sửa code lớn; không force-push.
