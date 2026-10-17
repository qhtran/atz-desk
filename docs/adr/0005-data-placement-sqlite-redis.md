# ADR 0005 — Chỗ để dữ liệu (đã chốt 1a)

- **Status:** Accepted (2026-10-17)
- **Quyết định chủ repo:** bền → SQLite; nóng → Redis; test → DB tạm / fixtures — **không** seed test vào DB production.

| Loại | Nơi |
|------|-----|
| User, vốn, risk %, prefs filter, signals, positions | SQLite `data/signals.db` |
| Quote / stream / pos:live | Redis (`vnstocks_realtime`) |
| pytest | `tmp_path` SQLite hoặc fixtures — không đụng VPS DB |

Triển khai tiếp: sổ vốn + risk per-user trên SQLite (CSV legacy chỉ migrate một lần nếu có).
