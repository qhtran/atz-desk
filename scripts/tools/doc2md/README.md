# doc2md — Office/PDF → Markdown (cho AI)

Tool nhỏ, độc lập app: chuyển `docx` / `xlsx` / `pdf` / … thành **Markdown sạch** + thư mục ảnh, để đưa vào chat AI **tiết kiệm token** hơn file Word gốc.

| Engine | Vai trò |
|--------|---------|
| **MarkItDown** (mặc định) | Convert chính (Microsoft) |
| **pandoc** (nếu có trên máy) | Fallback khi MarkItDown lỗi / rỗng |
| unzip Office | Lấy ảnh nhúng `word/media`, `xl/media`, `ppt/media` |
| sidecar | Copy ảnh nằm **cạnh** file nguồn (png/jpg/…) |

---

## 1. Cài một lần

Từ **root repo** `vnstocks`:

```bash
# Python deps
pip install -r scripts/tools/doc2md/requirements.txt

# (Khuyến nghị) pandoc — fallback
# macOS:
brew install pandoc
# Ubuntu/Debian:
# sudo apt-get install -y pandoc
```

Kiểm tra:

```bash
python scripts/tools/doc2md/convert.py --help
pandoc --version   # optional
```

---

## 2. Chạy (newbie)

### Một file Word

```bash
python scripts/tools/doc2md/convert.py \
  "/đường/dẫn/Mô tả công việc F2.docx" \
  -o docs/refs/_converted
```

### Ví dụ với file F2 (iCloud)

```bash
python scripts/tools/doc2md/convert.py \
  "$HOME/Library/Mobile Documents/com~apple~CloudDocs/StockRnD/refs/ideas_from_Hien/261017/Mô tả công việc thực hiện bản cập nhật F2.docx" \
  -o docs/refs/_converted
```

### Excel / PDF

```bash
python scripts/tools/doc2md/convert.py report.xlsx -o docs/refs/_converted
python scripts/tools/doc2md/convert.py slide-deck.pdf -o docs/refs/_converted
```

### Tuỳ chọn hữu ích

| Flag | Tác dụng |
|------|----------|
| `-o DIR` | Thư mục gốc output (mặc định `docs/refs/_converted`) |
| `--no-sidecar` | Không copy ảnh cạnh file nguồn |
| `--prefer-pandoc` | Thử pandoc trước MarkItDown |
| `--keep-empty-dirs` | Giữ `media/` / `sidecar/` dù trống |

---

## 3. Output trông như thế nào?

Với input `MoTa_F2.docx` (stem được slug hoá):

```
docs/refs/_converted/
  MoTa_F2/                 # hoặc tên stem đã làm sạch
    MoTa_F2.md             # Markdown + YAML frontmatter ngắn
    media/                 # ảnh nhúng trong Office (nếu có)
    sidecar/               # ảnh nằm cạnh file gốc (nếu có)
```

Đưa vào AI: **ưu tiên chỉ attach `*.md`**. Mở thêm `media/` / `sidecar/` khi cần nhìn plot/screenshot.

Frontmatter mẫu (đầu file `.md`):

```yaml
---
source: "/abs/path/file.docx"
format: "docx"
converted_at: "2026-10-17T11:00:00Z"
engine: "markitdown"
media_count: 0
sidecar_count: 3
content_sha256_10: "abc123...."
purpose: ai-consumable-markdown
---
```

Cuối file có mục `## Extracted media` với link relative `./media/...` / `./sidecar/...` nếu có ảnh.

---

## 4. Dùng MD với AI (tiết kiệm token)

1. Convert xong → mở file `.md`.
2. Copy nội dung (hoặc `@` file trong Cursor) thay vì upload `.docx`.
3. Nếu AI cần ảnh: chỉ đính kèm ảnh liên quan trong `sidecar/` / `media/`, không gửi cả bộ Office.

So với Word gốc: bỏ metadata Office, style rác, binary — context ngắn và ổn định hơn.

---

## 5. Định dạng hỗ trợ

`docx`, `doc`, `xlsx`, `xls`, `pptx`, `ppt`, `pdf`, `html`, `htm`, `csv`, `json`, `xml`, `txt`, `md`, `rtf`, `epub`, `msg`, `eml`

(Khả năng thực tế phụ thuộc MarkItDown / pandoc trên máy bạn.)

---

## 6. Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|-------------|------------|
| `markitdown chưa cài` | `pip install -r scripts/tools/doc2md/requirements.txt` |
| `ERR-DOC2MD-001 Không convert được` | Cài pandoc rồi chạy lại; hoặc `--prefer-pandoc` |
| Không thấy ảnh | Ảnh có thể **không nhúng** trong docx — chỉ nằm cạnh file → mặc định tool copy vào `sidecar/` |
| Tên file tiếng Việt / khoảng trắng | Luôn bọc path trong dấu `"..."` |
| Output không vào git | Cố ý: `docs/refs/_converted/` là artefact local; chỉ commit MD đã chỉnh tay nếu cần |

---

## 7. Test

```bash
pytest tests/test_doc2md.py -q
```

---

## 8. Không phải gì

- Không phải pipeline realtime của atz.vn.
- Không đọc/ghi secret.
- Không thay thế checklist tay (vd. `docs/F1_CHECKLIST_UI.md`) — chỉ sinh bản chữ + ảnh để AI/dev đọc nhanh.
