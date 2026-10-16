# Điều phối đa-bot (Cursor = Orchestrator)

## Vai trò

| Vai trò | Ai | Việc | Kênh |
|--------|-----|------|------|
| **Orchestrator** | Cursor (Composer) trong chat này | Hiểu mục tiêu user → chia việc → đọc kết quả → chốt ưu tiên `1a/1b…` → (tuỳ chọn) review diff | Chat Cursor + git |
| **Auditor** | AuditorBot (Grok + computer use) | Survey **atz.vn** / **fireant.vn**, báo cáo lệch UI/UX | `docs/auditorbot/inbox/` |
| **Coder / Ops** | VPSbot | Sửa code, test, commit, deploy VPS theo brief | `docs/bots/vpsbot/inbox/` → `outbox/` |
| **Chủ repo** | Bạn | Pull/push, auth, quyết định lớn, chuyển prompt cho bot ngoài Cursor | GitHub + chat |

**Nguyên tắc tiết kiệm token Cursor:** việc duyệt web dài, code/deploy lặp → giao bot. Cursor chỉ brief ngắn + đọc báo cáo/outbox + hỏi user khi cần.

---

## Luồng chuẩn

```
User yêu cầu
    ↓
Cursor [DBG] plan + lựa chọn số
    ↓
┌─────────────────┬──────────────────┐
│ AuditorBot      │ VPSbot           │
│ survey → inbox  │ code/deploy      │
│                 │ → outbox         │
└────────┬────────┴────────┬─────────┘
         ↓                 ↓
Cursor đọc inbox/outbox → tóm tắt user → Resolution / việc tiếp
```

1. Cursor ghi **brief** (Markdown) vào đúng inbox bot (hoặc đưa user copy prompt).
2. Bot làm việc → push kết quả.
3. User: `git pull` hoặc bảo Cursor *«đọc inbox auditor / outbox vps»*.
4. Cursor cập nhật Resolution, chuyển file đã xong sang `reports/` hoặc `outbox/archive/`.

---

## Khi nào Cursor tự làm (không giao bot)

- Sửa rất nhỏ / nóng (1 file, bug chặn production) mà VPSbot chưa sẵn.
- Verify 1 màn sau deploy (browser Cursor **ngắn**).
- Viết/chỉnh protocol, brief, template.
- Rủi ro: secret, nginx, SSH, firewall → **dừng, hỏi user**.

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
