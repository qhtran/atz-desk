# AuditorBot ↔ Cursor (VANTIQ / atz.vn) — giao tiếp qua repo

## Mục tiêu

Hai bot **không chat trực tiếp**. Chúng trao đổi qua Git:

| Vai trò | Bot | Việc |
|--------|-----|------|
| **Auditor** | AuditorBot (Grok + computer use) | Duyệt **atz.vn** và **fireant.vn**, ghi báo cáo Markdown vào repo |
| **Builder** | Cursor agent (Composer) | Đọc báo cáo → kế hoạch → sửa code → commit/merge/deploy VPS |

Chủ repo (bạn) chỉ cần: pull/push, hoặc bảo Cursor «đọc báo cáo mới nhất».

---

## Cấu trúc thư mục

```
docs/auditorbot/
  README.md                 # tài liệu này
  PROTOCOL.md               # quy tắc bắt buộc (đọc trước khi ghi)
  REPORT_TEMPLATE.md        # mẫu báo cáo
  inbox/                    # AuditorBot thả file mới (chưa xử lý)
  reports/                  # báo cáo đã xử lý / lưu trữ (Cursor hoặc bạn move vào)
```

**Quy ước tên file inbox:**

```
YYYYMMDD-HHMM-<site>-<topic>.md
```

Ví dụ:

- `20261017-0600-atz-realtime-board.md`
- `20261017-0615-fireant-vs-atz-colors.md`

---

## Vòng đời một báo cáo

1. **AuditorBot** khảo sát web → viết file theo `REPORT_TEMPLATE.md` → **commit + push** vào `docs/auditorbot/inbox/`.
2. **Bạn** (hoặc Cursor sau khi được bảo) `git pull`.
3. **Cursor** đọc file inbox → `[DBG] intent=plan` → lựa chọn `1a/1b…` → code/test/commit/deploy.
4. Cursor (hoặc bạn) **move** file từ `inbox/` → `reports/` và thêm mục **Resolution** (đã làm / không làm / hoãn) rồi commit.

Không force-push. Không sửa nginx/SSH trừ khi được yêu cầu rõ.

---

## Browser của Cursor (để hiểu đúng)

- Là **trình duyệt nhúng trong Cursor IDE** (automation: mở URL, click, snapshot).
- Dùng khi Cursor **tự kiểm chứng** UI atz.vn sau deploy.
- **Không** kết nối AuditorBot / Grok.
- AuditorBot dùng **computer use của Grok** — tách biệt hoàn toàn.

Hai đường survey có thể chạy song song; nguồn sự thật để sửa code vẫn là **file trong repo**.

---

## Prompt ngắn đưa AuditorBot

Copy nguyên khối trong `PROMPT_FOR_AUDITORBOT.md`.
