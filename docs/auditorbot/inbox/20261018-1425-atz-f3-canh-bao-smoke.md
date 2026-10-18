# Báo cáo AuditorBot

- **ID file:** `20261018-1425-atz-f3-canh-bao-smoke.md`
- **Task:** `docs/auditorbot/tasks/20261018-1425-f3-canh-bao-smoke.md` (P0, post T-232)
- **Ngày giờ (Asia/Ho_Chi_Minh):** 18/10/2026 14:26 (Chủ nhật, **ngoài phiên**; trang hiển thị "Ngoài phiên · Giờ HN 14:26 18/10/2026")
- **URL đã mở:**
  - atz: https://atz.vn → Danh mục → Watchlist → "Danh mục theo ngành (F3)" → Ngành = Ngân hàng
  - fireant: https://fireant.vn/ma-chung-khoan/VCB (optional)
- **Auth / ghi chú phiên:** đã login Authentik sẵn; desktop, viewport 1919×1112 CSS px (không phải 1280×800)
- **Công cụ:** Grok AuditorBot + computer use (read-only, không bấm nút hành động)

---

## 1. Tóm tắt

- **Smoke F3 Cảnh báo: PASS 7/7.** Có 11 nhóm ngành F3, bảng ngành có header «Cảnh báo», chuỗi đúng định dạng spec (`xu hướng ngày: …` ghép ` · `).
- Ngân hàng 20 mã: 16 mã có cảnh báo, 4 mã `—` (BVB, OCB, VAB, EVF — thiếu nến theo ghi chú trang).
- Không có CTA đặt lệnh/ticket trong ô Cảnh báo; không traceback.
- Ghi chú nhỏ (P2): một số chuỗi trùng mức giá (MBB 3 lần 19.5), cách diễn đạt "giảm thủng vùng hỗ trợ đỉnh" khó hiểu.
- FireAnt: không thấy UI cảnh báo thủng MA/BB tương đương → N/A.

---

## 2. Bảng đối chiếu / checklist

| # | Tiêu chí | Kết quả | Bằng chứng |
|---|----------|---------|------------|
| 1 | Sau auth vào Danh mục → Watchlist | Pass | Mục "Watchlist" là mặc định của Danh mục, không gặp trang login |
| 2 | Thấy nhóm ngành F3, chọn 1 ngành | Pass | Selectbox "Ngành" 11 nhóm: Chứng khoán, Ngân hàng, BĐS nhà ở, BĐS công nghiệp, Thép, Xây lắp-hạ tầng, Cảng biển-vận tải, Bán lẻ, Dầu khí, Hóa chất-cao su-nhựa, Hàng không; chọn Ngân hàng |
| 3 | Bảng có cột «Cảnh báo» | Pass | Header đúng 2 cột: `Mã`, `Cảnh báo`; vừa chiều ngang, không cần cuộn |
| 4 | ≥1 mã có chuỗi xu hướng/thủng/vượt, hoặc `—` ghi rõ mã | Pass | VD HDB: `xu hướng ngày: tăng · giảm thủng biên trên band 23.1 · giảm thủng vùng hỗ trợ đỉnh 23.4`; `—`: BVB, OCB, VAB, EVF |
| 5 | Không CTA đặt lệnh/ticket từ ô Cảnh báo | Pass | Grid không có link; dưới bảng chỉ có "Dùng cho Bộ lọc tín hiệu", "Đưa vào Trạm Trading" (không phải đặt lệnh) |
| 6 | Không crash/traceback | Pass | Không có hộp lỗi đỏ; chỉ info xanh "Chưa có danh mục riêng. Tạo một danh mục ở form trên." |
| 7 | Viewport + phiên | Pass (ghi nhận) | 1919×1112, ngoài phiên (CN 14:26) |
| — | FireAnt có UI tương tự | N/A | Trang VCB chỉ có MA10/20/50 overlay trên chart, không thấy cảnh báo thủng MA/BB (kiểm không exhaustive) |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

Header section: "Seed mentor F3 — cột Cảnh báo theo nến ngày (MA/BB/mây/đáy-đỉnh). Chỉ UI decision-support; không đặt lệnh. Thiếu nến → —."

| Mã | Cảnh báo |
|---|---|
| VCB | xu hướng ngày: giảm |
| BID | xu hướng ngày: giảm |
| CTG | xu hướng ngày: giảm |
| TCB | xu hướng ngày: tăng |
| HDB | xu hướng ngày: tăng · giảm thủng biên trên band 23.1 · giảm thủng vùng hỗ trợ đỉnh 23.4 |
| MBB | xu hướng ngày: sideway · vượt kháng cự MA20 19.5 · vượt kháng cự band giữa 19.5 · vượt kháng cự biên dưới mây 19.5 |
| VPB | xu hướng ngày: tăng |
| STB | xu hướng ngày: giảm |
| LPB | xu hướng ngày: giảm · vượt kháng cự vùng đáy 37.2 |
| EIB | xu hướng ngày: sideway |
| ACB | xu hướng ngày: giảm · vượt kháng cự vùng đáy 20.1 |
| MSB | xu hướng ngày: tăng |
| VIB | xu hướng ngày: tăng |
| TPB | xu hướng ngày: giảm |
| SHB | xu hướng ngày: giảm |
| SSB | xu hướng ngày: giảm |
| BVB | — |
| OCB | — |
| VAB | — |
| EVF | — |

- Sidebar "Vị thế hiện tại" cũng có cột Cảnh báo: TPB `—`, POW `—` (lưu ý: TPB trong bảng ngành có `xu hướng ngày: giảm` nhưng sidebar `—` → nguồn/điều kiện tính có thể khác nhau).
- Grid là Glide canvas; dữ liệu đọc qua bảng accessibility ẩn + đối chiếu screenshot.

### 3.2 fireant.vn

- Trang mã VCB: chart có MA10/20/50 trong legend; không thấy text/badge cảnh báo thủng MA/Bollinger. → N/A, không tính Fail.

---

## 4. Đề xuất cho Cursor (không có Fail — chỉ P2)

1. `[P2]` Sidebar "Vị thế hiện tại" TPB hiển thị `—` trong khi bảng ngành có `xu hướng ngày: giảm` — **Done khi:** cùng mã cho cùng chuỗi Cảnh báo ở cả 2 nơi (hoặc ghi chú lý do khác).
2. `[P2]` Gộp các mốc trùng giá (MBB: MA20/band giữa/biên dưới mây cùng 19.5) thành 1 cụm, vd `vượt kháng cự 19.5 (MA20, band giữa, mây)` — **Done khi:** không còn ≥2 mệnh đề cùng hướng cùng mức giá trong 1 ô.
3. `[P2]` Làm rõ wording "giảm thủng vùng hỗ trợ đỉnh" / mâu thuẫn bề ngoài "xu hướng tăng · giảm thủng biên trên band" (HDB) + tooltip/giải thích `—` (thiếu bao nhiêu nến) cho BVB/OCB/VAB/EVF — **Done khi:** spec F3_ALERTS có bảng thuật ngữ và UI dùng đúng thuật ngữ đó.

---

## 5. Việc không nên làm

- Không thêm CTA đặt lệnh vào ô Cảnh báo (đúng spec decision-support).
- Không cố bắt chước FireAnt cho cột này (FireAnt không có tương đương).

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
