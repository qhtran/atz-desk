# Cursor User keybindings / tasks (macOS)

Bản sao cấu hình Cursor **User** (không phải workspace), dùng để khôi phục máy mới hoặc sau khi reset.

## Nội dung

| File | Mục đích |
|------|----------|
| `keybindings.json` | Typora (`Cmd+Shift+O` trên `.md`), Home/End kiểu Windows, keymap PyCharm/Cursor lai |
| `tasks.json` | Task `Open in Typora` (đi kèm phím tắt Typora) |

## Khôi phục

```bash
USER_DIR="$HOME/Library/Application Support/Cursor/User"
cp .cursor/user-backup/keybindings.json "$USER_DIR/keybindings.json"
cp .cursor/user-backup/tasks.json "$USER_DIR/tasks.json"
```

Sau đó reload Cursor nếu cần (`Cmd+Shift+P` → Reload Window).

## Lưu ý

- File gốc nằm ngoài repo: `~/Library/Application Support/Cursor/User/`
- Home/End dùng `cursorHome`/`cursorEnd` (override IntelliJ `cursorLineStart`/`cursorLineEnd`)
- `cursorEnd` không có smart End theo trailing whitespace (giới hạn VS Code/Cursor)
