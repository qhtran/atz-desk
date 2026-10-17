# Báo cáo AuditorBot — F1 acceptance baseline (atz.vn vs FireAnt)

- **ID file:** `20261017-0622-atz-f1-acceptance-baseline.md` (task `tasks/20261017-0622-f1-acceptance-baseline.md`)
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 ~06:40–06:55 (ngoài phiên, giá đứng yên); viết báo cáo ~07:00
- **URL đã mở:**
  - atz: `https://atz.vn` → Tổng quan, Realtime/Bảng giá, Bộ lọc tín hiệu, Tin tức/Bài viết, sidebar «Tổng quan vị thế của bạn»
  - fireant: `https://fireant.vn/thi-truong`, `https://fireant.vn/ma-chung-khoan/VIC`
- **Auth / ghi chú phiên:** cả hai đã login, không gặp trang đăng nhập. Desktop 1280px + thu hẹp (zoom 300% ≈ 427 CSS px). Chỉ đọc: không bấm Chạy lọc / Lưu cấu hình / Quét và làm mới / Thêm cảnh báo; chỉ gõ thử ô Tìm mã rồi xoá.
- **Công cụ:** Grok AuditorBot + computer use + đọc code `main` @ `0816526` (chỉ đọc)
- **Quy ước:** `[live]` = thấy trên UI thật; `[code]` = suy ra từ code, chưa thấy trên UI. Màu hex là **ước lượng bằng mắt** từ screenshot, chưa lấy mẫu pixel.

> Bối cảnh: atz là công cụ **kỷ luật + tín hiệu**, không phải bản sao FireAnt. Đối chiếu chỉ để chọn phần đáng học.

---

## 1. Tóm tắt

1. **P0 [live] — dữ liệu Top 20 KL trên Tổng quan lệch phiên:** MBB Tổng quan 19.90 **xanh +2.84%** nhưng Realtime 19,850 **đỏ −0.25%** (FireAnt 19.85 −0.25%). VHM Tổng quan 58.90 **đỏ −3.44%** nhưng Realtime/FireAnt 61.00 **+3.57%**. Lệch giá thêm ở VIC, TPB, SSI, CTG, GAS, PLX, POW. Bảng không có mốc thời gian dữ liệu. Hunch [code]: `rank_volume_leaders()` đọc OHLCV cục bộ chỉ được làm tươi khi bấm «Quét và làm mới dữ liệu» — cần Cursor xác minh.
2. **P0 [live] — thẻ VNIndex Tổng quan lệch Realtime:** Tổng quan TC 1,719.42 / đóng 1,704.87 / −0.85% (đỏ) vs Realtime 1,705.91 +7.56 / +0.45% (xanh). Bản tin ghi đóng cửa 15/10 = 1,698.35, khớp TC ngầm của Realtime, không khớp Tổng quan.
3. **P1 [live]:** Bảng giá vẫn hiện Trần/Sàn dạng `22000.000000` (đã báo ở report 0600, chưa sửa). Mọi dòng vẫn `live` ngoài giờ.
4. **Pass [live]:** màu tăng/giảm/TC đúng hướng trên Realtime; RSS không lộ HTML (D2 Pass); Bộ lọc tín hiệu load không lỗi; sidebar có vốn/NAV/vị thế, giá TPB khớp board và FireAnt. Banner TypeError chunk không tái hiện lần này (lần trước trong cùng phiên có `Html.CGCC7X4P.js` trên Tin tức → lỗi chập chờn).
5. **BLOCKED:** trần/sàn (tím/xanh dương) không quan sát được (`trần 0 · sàn 0`, FireAnt cũng không thấy mã trần/sàn); flash/độ trễ cần đo trong phiên.

---

## 2. Bảng đối chiếu

| # | Tiêu chí | FireAnt | atz / VANTIQ | Lệch? | Tag | Loại |
|---|---|---|---|---|---|---|
| A1–A3 | Màu tăng/giảm/TC (Realtime) | Xanh ≈#22C55E, đỏ ≈#EF4444, vàng ≈#FACC15 | Xanh ≈#16A34A, đỏ ≈#DC2626, vàng ≈#CA8A04 [live]. Đúng hướng; hex nhìn tối hơn token `#00C853/#FF3D00/#FFC107` trong `docs/COLOR_TOKENS.md` (chưa đo pixel) | Hướng: Không. Hex: cần đo | — (P2 nếu đo pixel lệch) | — |
| A4–A5 | Trần tím / sàn xanh dương | Không thấy mã trần/sàn (đã duyệt 47/50 dòng) | Caption `trần 0 · sàn 0`, legend «tím=trần · xanh dương=sàn» [live] | Không quan sát được phiên này | BLOCKED (chờ phiên có trần/sàn) | — |
| A* | Màu/dấu Top 20 KL (Tổng quan) | MBB −0.25% đỏ, VHM +3.57% xanh | MBB +2.84% xanh, VHM −3.44% đỏ [live] | **Có** | **P0** | Thiếu SP (dữ liệu cũ/không timestamp) |
| — | Thẻ VNIndex Tổng quan | 1705.91 +7.56 (+0.45%) | 1,704.87 −14.55 (−0.85%), TC 1,719.42 [live] | **Có** | **P0** | Thiếu SP (dữ liệu) |
| — | Format Trần/Sàn bảng giá | (trang mã) 2 số lẻ | `22000.000000`, `233200.000000` trong khi Giá là `20,600` [live] | Có | P1 | Thiếu SP (format) |
| — | Trạng thái dòng ngoài giờ | — | 30/30 dòng `live`, header «Ngoài giờ giao dịch» [live] | Có | P1 | Thiếu SP |
| B1 | Search mã | Ô header, dropdown gợi ý theo từng ký tự | «Tìm mã nhanh» lọc đúng (`FP`/`FPT` → 1/30) **chỉ sau Enter** («Press Enter to apply») [live] | Có (UX) | P1 | Giới hạn Streamlit (`st.text_input` chỉ commit khi Enter/blur) |
| B2 | Cập nhật | — | Mốc quote nhảy mỗi phút 06:48:27→06:51:27, giá không đổi (ngoài phiên) [live] | Không (ngoài phiên) | — | — |
| B3 | Flash | Chưa đo (ngoài phiên) | Không thấy trong screenshot; có CSS flash [code] | ? | BLOCKED | Cần đo trong phiên |
| C1 | Sidebar vốn/NAV/mã | — | Tổng vốn 100,000,000; GTCK 49,921,721; Tiền mặt 50,000,000; NAV 99,921,721 (badge đỏ `-78279`); TPB, POW [live] | Không | Pass | — |
| C2 | Giá HT sống | TPB 12.00, POW 12.20 | TPB 12.00 = board 12,000 ✓. POW 12.20 (không có trên board 30 mã). Ghi chú «Redis 1/2» không giải thích [live] | Nhẹ | P1 | Thiếu SP (nhãn) |
| C3 | Cảnh báo HT/KC/±% | — | Cả 2 dòng `—` (TPB +1.7%, POW −2.0% so giá mua → chưa chạm mốc 5/8/10%) [live + code `sidebar_portfolio.py:30-60`] | Không kết luận | — | — |
| D1 | Top KL | — | Có, 20 dòng, không crash [live]; nhưng dữ liệu lệch (xem A*), có dòng `VNINDEX 1704.87` lẫn trong danh sách cổ phiếu, không dấu phẩy | Có | P0 (dữ liệu) / P1 (VNINDEX lẫn) | Thiếu SP |
| D2 | RSS không HTML thô | Tin VIC đọc được | 50 tin/5 trang, quét text: 0 thẻ/entity [live] | Không | **Pass** | — |
| — | Lỗi chunk JS | Không | Không tái hiện sau hard reload; trước đó cùng phiên thấy `Failed to fetch dynamically imported module: …/static/js/Html.CGCC7X4P.js` trên Tin tức [live] | Chập chờn | P1 | Thiếu SP (cache deploy) |
| — | Mobile/hẹp | Bảng → thẻ (Mã, Giá, %), ẩn cột phụ | Sidebar thu «»; bảng giá cuộn ngang, mất Sàn giá/Sàn/Nguồn/Lúc/Trạng thái; Top 20 cắt ở Xu hướng [live] | Có | P2 | Một phần giới hạn Streamlit (`st.dataframe` không responsive theo cột) |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Tổng quan — Top 20 khối lượng phiên [live]:** cột Mã | Giá | KL phiên | KL TB 10 phiên | KL/TB10 | Biến động giá (%) | Xu hướng. So với Realtime (cùng lúc): MBB 19.90 (+2.84) vs 19,850 (−0.25); VHM 58.90 (−3.44) vs 61,000 (+3.57); VIC 218.00 vs 215,000; TPB 11.75 vs 12,000; SSI 19.25 vs 19,450; CTG 29.80 vs 30,600; GAS 76.20 vs 76,100; PLX 35.55 vs 35,050; POW 12.20 −2.01% vs FireAnt 12.20 0.00%. Nhiều giá Tổng quan trùng TC của phiên 16/10 (vd VIC 218.00 = TC FireAnt) → khả năng hiển thị **phiên trước** mà không ghi ngày.
- **[code]** `src/atz/ui/overview_page.py:524-554` `show_volume_leaders()` gọi `analysis.volume_leaders.rank_volume_leaders()`; message rỗng nhắc «Bấm «Quét và làm mới dữ liệu» để cập nhật OHLCV» → nguồn là OHLCV cục bộ, không phải Redis quote. Caption không có mốc ngày dữ liệu.
- **Tổng quan — Chỉ số VN [live]:** VNIndex TC 1,719.42 / đóng 1,704.87 / −0.85%; HNX 259.29/259.13; UPIndex 124.15/124.87 (+0.58%); VN30 1,843.71/1,855.41. VNIndex lệch Realtime/FireAnt; các chỉ số khác khớp.
- **Realtime — Bảng giá [live]:** caption nguyên văn `Cập nhật lúc 06:51:32 · tự cập nhật mỗi 30s · quote mới nhất 06:51:27 · hiện 30/30 mã · trần 0 · sàn 0 · limit API 30/30 · spark cache 30 · tím=trần · xanh dương=sàn · xanh/đỏ/vàng=Δ`. 15 cột: Mã, Giá, +/-, %, Xu hướng, Mở, Cao, Thấp, TC, Trần, Sàn giá, Sàn, Nguồn (KBS), Lúc, Trạng thái. Hai cột tên dễ nhầm: «Sàn giá» (giá sàn) và «Sàn» (HOSE). Màu đúng hướng: ACB/HDB/SAB/STB 0 vàng; GAS/MBB/PLX/VIC đỏ; còn lại xanh. Toàn bộ khớp FireAnt.
- **Search [live]:** gõ `FP` không lọc cho tới khi Enter; sau Enter caption `hiện 1/30 mã · limit API 1/1`, chỉ còn FPT 58,200. Xoá + Enter → 30/30.
- **Bộ lọc tín hiệu [live]:** load OK: «Tiêu chí lọc (catalog F1)», «Chế độ: Lọc tự do | Top 5 mỗi ngành», nút Lưu cấu hình/Chạy lọc/Tải JSON/Nhập JSON.
- **Tin tức [live]:** «Nguồn mặc định: RSS CafeF · Thị trường chứng khoán. Tự làm mới mỗi 30 phút. 10 tin mỗi trang.» «Trang 1/5 · 50 tin». Không thấy thẻ HTML/entity. [code] đã có `datasource/rss_html.sanitize_rss_html`.
- **Sidebar [live]:** «Ngoài phiên · Giờ HN 06:50 17/10/2026». TPB giá mua 11.80 / HT 12.00; POW 12.45 / 12.20. Ghi chú «Giá HT: Redis 1/2 (nghìn đồng)» — [code] `live_quotes.load_live_prices_thousands` + fallback OHLCV ⇒ nhiều khả năng POW là Redis miss (không thuộc 30 mã ingest) nên dùng OHLCV; UI không nói mã nào fallback.
- **Hẹp ~427px [live]:** index cards xếp dọc; bảng giá cuộn ngang, mất 5 cột cuối; Top 20 cắt ở Xu hướng.

### 3.2 fireant.vn

- `/thi-truong` [live]: 50 dòng (chọn 20/50/100), 11 cột (#, Mã CK, ☆, Giá, +/-, %, Vốn hóa, GT, Tổng KL, GT NN mua ròng, Biểu đồ), ~13 dòng/màn. Màu: xanh ≈#22C55E, đỏ ≈#EF4444, 0.00 vàng ≈#FACC15. Không thấy mã trần/sàn (dòng 14–16 không soát riêng).
- Search header: focus mở «Mã gần đây»; gõ hiện «Kết quả tìm kiếm» theo từng ký tự (không cần Enter).
- `/ma-chung-khoan/VIC` [live]: 215.00 đỏ, −3.00/−1.38%, TC 218.00 vàng, «Cập nhật lúc 15:30:28». 5 tin có giờ tương đối, đọc sạch.
- Mobile ~256px [live]: bảng thành thẻ (Mã + tên, ☆, Giá/% xếp chồng), ẩn cột phụ; banner «TẢI APP» đè list.

---

## 4. Đề xuất cho Cursor (tối đa 5, đo được)

1. `[P0]` Top 20 KL Tổng quan: dùng giá/Δ% phiên hiện tại (Redis quote hoặc board) **hoặc** ghi rõ «Dữ liệu phiên dd/mm» + mốc quét trong caption. **Done khi:** cùng thời điểm, Giá và dấu % của MBB/VHM/VIC trên Top 20 khớp bảng Realtime (±1 bước giá), hoặc caption hiện ngày phiên khác hôm nay.
2. `[P0]` Thẻ VNIndex Tổng quan dùng cùng nguồn/TC với Realtime. **Done khi:** VNIndex đóng cửa & Δ trên Tổng quan = Realtime (±0.01 điểm) ngoài phiên.
3. `[P1]` Format Trần/Sàn/TC như cột Giá (`{:,.0f}`) hoặc ẩn bằng `column_config`; đổi nhãn «Sàn» (sàn GD) thành «Sàn GD» để khỏi nhầm «Sàn giá». **Done khi:** không còn ô dạng `22000.000000` trên Bảng giá.
4. `[P1]` Ngoài giờ: trạng thái dòng `cuối phiên`/`đóng cửa` thay `live`; sidebar ghi rõ mã nào dùng OHLCV khi Redis miss (thay «Redis 1/2»). **Done khi:** 06:45 không dòng nào `live`; POW có nhãn «OHLCV» trong sidebar.
5. `[P1]` Bỏ `VNINDEX` khỏi danh sách cổ phiếu Top 20 (hoặc tách riêng), và theo dõi lỗi chunk chập chờn (cache `index.html`/`/static`). **Done khi:** Top 20 chỉ chứa mã cổ phiếu; 3 lần hard reload sau deploy mới không còn `Failed to fetch dynamically imported module`.

(P2 để sau: search lọc theo từng ký tự cần custom component/keyup — giới hạn Streamlit; bố cục thẻ cho mobile; đo pixel màu so token.)

---

## 5. Việc không nên làm

- Đừng chỉnh màu theo hex FireAnt — giữ token `COLOR_TOKENS.md`; chỉ sửa nếu đo pixel cho thấy lệch token.
- Đừng kết luận về flash/độ trễ hay trần/sàn tím-xanh dương khi chưa có phiên 09:15–14:45 với mã chạm trần/sàn.
- Đừng hack JS để search lọc theo từng phím trên `st.text_input` (BLOCKED); nếu cần, đánh giá component riêng.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
