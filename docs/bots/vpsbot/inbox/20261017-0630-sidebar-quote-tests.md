# Brief VPSbot — siết test sidebar quote

- **ID:** `20261017-0630-sidebar-quote-tests.md`
- **Từ:** Orchestrator (overnight)
- **Ưu tiên:** P1
- **deploy:** no
- **merge_main:** yes
- **infra:** no
- **Phụ thuộc:** xong `20261017-0622-sidebar-live-quote` (hoặc code đã có trên main)

---

## Mục tiêu

Unit/integration test cho đường giá sidebar: Redis hit, Redis miss → OHLCV fallback, symbol không có, quote stale (nếu có flag).

## Phạm vi

- `tests/test_sidebar_portfolio.py` (tạo nếu chưa) và/hoặc helper mới
- Mock Redis — không cần Redis thật trong CI local
- Không đổi UX lớn ngoài chỗ test đòi hỏi

## Done khi

1. `pytest` module Pass
2. Push + merge main
3. Outbox `…-0630-sidebar-quote-tests-DONE.md`
