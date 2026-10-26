# Nhắc — thứ Hai 2026-10-26 · Kiểm tra sổ lệnh HĐTL (dev.atz.vn)

**Mục đích:** Xác nhận bước cuối sau prep depth VN30F1M (commit `6fe7f21` + skeleton `kind` equity).

**Khi nào:** Trong giờ giao dịch (sáng 9h–11h30 hoặc chiều 13h–15h, giờ VN).

## Checklist (5 phút)

1. Mở https://dev.atz.vn/ → tab **Giao dịch iBoard** → chọn **VN30F1M**.
2. (Tuỳ chọn) Thêm `?fake_depth=0` vào URL — tắt số M/B tạm nếu chưa có tin SSI.
3. Quan sát cột **mua 1–3 / bán 1–3** và khối lượng:
   - **Pass:** số **đổi theo thời gian** (không cố định mãi một kiểu “giả”).
   - **Chưa pass:** M/B trống hết (ngoài giờ / SSI chưa gửi sổ) → thử lại trong phiên; hoặc vẫn thấy pattern lặp y chang mọi lần tải trang → báo agent (capture tin SSI).
4. Lặp nhanh tab **VN30F2M** nếu cần.

## Gợi ý câu mở chat

```text
Pull. Đọc docs/agents/REMIND_2026-10-26_HDL_DEPTH.md. Báo kết quả checklist phiên HĐTL.
```

Sau khi pass: Master có thể ack / đóng mục HANDOFF «verify phiên mở».

---

## Kết quả sprint C (ATZ Desk)

| Ngày | Phiên | VN30F1M | VN30F2M | Ghi chú |
|------|-------|---------|---------|---------|
| 2026-10-27 | Ngoài giờ (deploy đêm) | **Chưa verify live** | **Chưa verify live** | Code path: `enrichDepth` + `applyEquity` + prep `6fe7f21` — **Pass checklist trong giờ 9–15 VN** để đóng C |

**Verify tự động (ops):** Sau phiên, `docker exec atz-redis-dev redis-cli HGET priceboard:quotes VN30F1M` — nếu JSON có `bid1`/`ask1` thay đổi giữa hai lần curl cách 30s → Pass.

**Spec:** [`docs/specs/PRICEBOARD_P1_DEPTH_NN.md`](../specs/PRICEBOARD_P1_DEPTH_NN.md)
