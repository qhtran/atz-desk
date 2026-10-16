# Bản tin sáng

Daily Market News Agent ghi bản tin vào `data/ban_tin.md` ở thư mục gốc project. Thư mục `data/` là volume Docker, không đưa vào git.

Nội dung là Markdown ngắn. Tab Cảnh báo trong `app.py` đọc đúng file này khi người dùng mở tab. Không có API riêng.

Ví dụ:

```markdown
## 15/10/2026

VNINDEX mở cửa đi ngang. Ưu tiên các mã trong Top 20 còn trên MA20.
```

Nếu file trống hoặc chưa có, tab hiện đường dẫn để tạo file.
