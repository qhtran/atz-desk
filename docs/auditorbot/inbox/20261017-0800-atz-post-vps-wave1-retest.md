# Báo cáo AuditorBot — Retest sau VPSbot wave1 (C1–C3, E1–E2, D1, A1–A3)

- **ID file:** `20261017-0800-atz-post-vps-wave1-retest.md` (task `tasks/20261017-0800-post-vps-wave1-retest.md`)
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 07:59–08:03 (thứ Bảy, ngoài phiên; dữ liệu phiên 16/10); viết báo cáo ~08:05
- **Phụ thuộc:** task `0622`, `0630` (colors, rss), `0700` đã có báo cáo trên các nhánh `auditor/20261017-*` → không làm lại. `git log fe9450e..edf205d`: chỉ đổi docs → code live cho sidebar/board/overview = `main` @ `fe9450e` (giống lần retest 0700).
- **URL đã mở:**
  - atz: `https://atz.vn` → Tổng quan (sidebar «Tổng quan vị thế của bạn», bảng «Top 20 khối lượng phiên», «Chỉ số Việt Nam»), Realtime → Bảng giá (ô «Tìm mã nhanh»)
  - fireant: `https://fireant.vn/ma-chung-khoan/TPB`, `https://fireant.vn/ma-chung-khoan/POW`
- **Auth / ghi chú phiên:** cả hai đã login, không gặp trang đăng nhập. Desktop 1280×800. Chỉ đọc: chuyển menu, gõ/xoá filter mã.
- **Công cụ:** Grok AuditorBot + computer use + đọc code `main` (chỉ đọc)
- **Quy ước:** `[live]` = thấy trên UI thật; `[code]` = suy ra từ code; `[calc]` = tính lại từ số live. Màu hex là **ước lượng bằng mắt**, chưa đo pixel (board/Top 20 là canvas grid).

---

## 1. Tóm tắt

1. **Không regression sau wave1 [live]:** C1, C2, E1, E2, A1–A3 Pass; số sidebar và màu board giống hệt retest 07:30 (22 xanh / 4 đỏ / 4 vàng / 0 trần / 0 sàn). Không banner lỗi, không traceback; board tự làm tươi 30s không giật hình.
2. **P0 mới [live] — dữ liệu «Top 20 khối lượng phiên» lệch phiên:** cùng mã, cùng màn hình đưa hướng ngược nhau. MBB Top 20: 19.90 **xanh +2.84%**; board realtime: 19,850 **đỏ −0.25%**. POW Top 20: −2.01%, KL 11,371,900; FireAnt phiên 16/10: 0.00%, KL 4,843,200. TPB KL Top 20 11,575,100 vs FireAnt 18,806,500. Nghi bar cuối/bar trước trong `data/ohlcv/*.csv` không phải 16/10–15/10 (thiếu ngày hoặc dữ liệu cũ) — **hunch, cần kiểm file CSV trên VPS**.
3. **P1 mới [live] — VNINDEX mâu thuẫn giữa 2 trang:** Tổng quan «Chỉ số Việt Nam»: TC 1,719.42, đóng cửa 1,704.87, **−14.55 / −0.85%**; card Realtime: 1,705.91, **+7.56 / +0.45%** (TC ngầm ≈ 1,698.35 [calc]). Chưa xác minh bên nào đúng. Ngoài ra VNINDEX lọt vào Top 20 như một mã cổ phiếu (dòng 19).
4. **D1 Pass có điều kiện [live]:** bảng 20 dòng, sparkline render đủ, không crash; nhưng số liệu sai như mục 2 → Pass về hiển thị, **Fail về dữ liệu**.
5. **Còn nguyên từ 0700 [live]:** POW (đang nắm giữ) không có trên board 30 mã, sidebar «Redis 1/2»; C3 vẫn «—»; bar lãi/lỗ một màu xanh dương, tooltip float thô (`423728.813559`); cột Trần/Sàn `22000.000000`.

---

## 2. Bảng đối chiếu (Pass/Fail theo `docs/bots/ACCEPTANCE_TESTS.md`)

| ID | Tiêu chí | FireAnt [live] | atz / VANTIQ | Kết quả | Tag | Loại |
|---|---|---|---|---|---|---|
| A1 | Mã tăng xanh | TPB +2.13% xanh | 22 mã xanh, vd BID 33,950 +750 +2.26%, VHM 61,000 +2,100 +3.57%; màu ≈ `#1FA34F` (mắt) [live] | **Pass** (ngữ nghĩa; hex chưa đo so `#00C853`) | — | — |
| A2 | Mã giảm đỏ | — | GAS 76,100 −0.13%, MBB 19,850 −0.25%, PLX 35,050 −1.41%, VIC 215,000 −1.38%; ≈ `#E03E2D` (mắt) | **Pass** (hex chưa đo so `#FF3D00`) | — | — |
| A3 | Tham chiếu vàng | POW 0.00% | ACB 20,600, HDB 22,800, SAB 43,000, STB 62,800 (+0/0.00%); ≈ `#D9A300` (mắt) | **Pass** (hex chưa đo so `#FFC107`) | — | — |
| C1 | Khối vị thế có vốn/NAV/mã | — | Vốn 100,000,000; GTCK 49,921,721; Tiền mặt 50,000,000; NAV 99,921,721, badge đỏ «↓ -78279»; TPB, POW | **Pass** | — | — |
| C2 | Giá HT / Notes phiên nghỉ | TPB 12.00, POW 12.20 (15:30 16/10) | TPB 12.00, POW 12.20; caption «Ngoài phiên · Giờ HN 07:59» + «Giá HT: Redis 1/2» | **Pass (phiên nghỉ)** | P1 (nhãn nguồn từng mã — như 0700) | Thiếu SP |
| C3 | Cảnh báo HT/KC / ±% | — | Cả 2 dòng «—» (TPB +1.69%, POW −2.01% [calc] < mốc 5%) | **Không kết luận** | P1 | Thiếu SP |
| D1 | Top KL ~20 mã, không crash | TPB KL 18,806,500; POW KL 4,843,200, 0.00% | 20 dòng, sparkline OK, không lỗi; nhưng TPB KL 11,575,100, POW KL 11,371,900 −2.01%, MBB +2.84% (board −0.25%) | **Pass hiển thị / Fail dữ liệu** | **P0** | Thiếu SP (dữ liệu OHLCV) |
| E1 | Sidebar khớp hướng board | TPB +2.13% | TPB sidebar 12.00 = board 12,000 +250 +2.13% TC 11,750; POW «Không có mã khớp «POW».» | **Pass** (TPB) / **N/A** (POW) | P1 (POW) | Thiếu SP (rổ ingest) |
| E2 | Không regression màu | — | 22/4/4/0/0, từng mã khớp retest 0700 | **Pass** | — | — |
| — | VNINDEX nhất quán giữa trang | (không mở) | Tổng quan −0.85% vs Realtime +0.45% | Có | P1 | Thiếu SP (2 nguồn chỉ số) |
| — | VNINDEX trong Top 20 cổ phiếu | — | Dòng 19: VNINDEX 1704.87, KL 584,041,036 | Có | P2 | Thiếu SP |
| — | Đơn vị giá giữa màn hình | nghìn (12.00) | Top 20/sidebar nghìn (19.90); board đồng (19,850) | Có | P2 | Thiếu SP |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Sidebar [live 07:59–08:02]:** «Ngoài phiên · Giờ HN 07:59 17/10/2026». «Vị thế hiện tại»: TPB 11.80 | 12.00 | —; POW 12.45 | 12.20 | —; chữ Giá HT màu trung tính. Caption «Giá HT: Redis 1/2 (nghìn đồng). Tham chiếu: https://rtboard.hsx.vn/». Bar «Lãi lỗ ước lượng từng mã trên NAV phân bổ»: TPB ≈ +423,729, POW ≈ −502,008, cùng màu xanh dương; tổng −78,279 = badge NAV [calc].
- **Top 20 khối lượng phiên [live]:** bảng luôn hiện (không phải expander), cột Mã | Giá | KL phiên | KL TB 10 phiên | KL/TB10 | Biến động giá (%) | Xu hướng, sắp theo KL/TB10. 5 dòng đầu: MBB 19.90 · 32,621,600 · 11,359,870 · 2.87× · +2.84; POW 12.20 · 11,371,900 · 4,811,070 · 2.36× · −2.01; STB 62.80 · 6,617,700 · 3,529,760 · 1.87× · −2.79; HCM 24.00 · 4,644,700 · 2,519,050 · 1.84× · +3.90; DXG 10.25 · 13,619,100 · 7,823,280 · 1.74× · +2.50. Dòng 19 là VNINDEX.
- **Mâu thuẫn chéo [live]:** STB Top 20 −2.79% nhưng board STB 62,800 vàng 0.00%; MBB Top 20 +2.84% nhưng board −0.25%; POW −2.01% nhưng FireAnt 0.00% (−2.01% trùng % 1 tuần FireAnt của POW).
- **[code] `src/atz/analysis/volume_leaders.py`:** chỉ đọc OHLCV local (`data/ohlcv`); `KL phiên` = `volume.iloc[-1]`, `Biến động giá` = `close[-1]/close[-2] − 1`. Không kiểm ngày của bar cuối, không kiểm 2 bar liên tiếp có phải 2 phiên kề nhau, không loại mã chỉ số (VNINDEX). → Nếu CSV thiếu ngày/chưa cập nhật, bảng ra số sai mà không báo.
- **Board realtime [live 08:00:42]:** «Cập nhật lúc 08:00:42 · tự cập nhật mỗi 30s · quote mới nhất 08:00:40 · hiện 30/30 mã · trần 0 · sàn 0 · limit API 30/30 · spark cache 30 · …». Làm tươi 08:01:12/08:01:42/08:02:05/08:02:18 không giật. Filter `TPB` → 1/30 (Trần `12550.000000`, Sàn `10950.000000`, KBS, live); `POW` → «Không có mã khớp «POW».»; xoá filter → 30/30.
- **Card chỉ số Realtime [live]:** VNINDEX 1,705.91 +7.56/+0.45%; HNXINDEX 259.13 −0.16/−0.06%; UPCOMINDEX 124.87 +0.72/+0.58%; VN30 1,855.41 +11.70/+0.63%.
- **Tải trang:** vài giây skeleton + «Đang lấy chỉ số...», sau đó ổn định.

### 3.2 fireant.vn

- **TPB [live]:** 12.00, +0.25/+2.13%, TC 11.75, Mở 11.85, 11.75–12.25, KL 18,806,500, «Cập nhật lúc 15:30:24».
- **POW [live]:** 12.20, 0.00/0.00%, TC 12.20, Mở 12.30, 12.10–12.35, KL 4,843,200, «Cập nhật lúc 15:30:18». Widget Thảo luận hiện «Error! Oops, something went wrong» (lỗi phía FireAnt, không liên quan atz).

---

## 4. Đề xuất cho Cursor (tối đa 5, đo được)

1. `[P0]` Kiểm và sửa dữ liệu Top 20 KL: in ngày của 2 bar cuối từng mã trong `data/ohlcv`, bỏ mã có bar cuối ≠ phiên giao dịch gần nhất hoặc 2 bar không kề nhau, hiện ngày phiên trong tiêu đề bảng. **Done khi:** ngoài phiên 17/10, TPB KL phiên = 18,806,500 (±1% so FireAnt), POW 0.00%, MBB cùng hướng với board; tiêu đề ghi «phiên 16/10».
2. `[P1]` Thống nhất VNINDEX giữa Tổng quan và Realtime (cùng nguồn/cùng TC, hoặc ghi rõ nguồn + giờ). **Done khi:** hai màn hình cùng giá, cùng Δ và cùng dấu cho VNINDEX ngoài phiên.
3. `[P1]` Loại mã chỉ số (VNINDEX, HNXINDEX, VN30…) khỏi Top 20 cổ phiếu. **Done khi:** Top 20 không có dòng nào bắt đầu bằng chỉ số.
4. `[P1]` (giữ từ 0700) Mã desk luôn có quote + nhãn nguồn từng dòng sidebar. **Done khi:** trong phiên caption «Redis 2/2», board lọc `POW` ra 1 dòng, dòng POW có nhãn nguồn.
5. `[P2]` Định dạng Trần/Sàn như cột giá khác và tô bar lãi/lỗ theo dấu, làm tròn tooltip. **Done khi:** Trần TPB hiện `12,550`; bar TPB xanh, POW đỏ; tooltip `+423,729`.

---

## 5. Việc không nên làm

- Đừng sửa màu Top 20 để «khớp board» khi chưa sửa dữ liệu — lỗi nằm ở bar OHLCV, không ở bảng màu.
- Đừng thêm refresh nhanh hơn cho Top 20; bảng dùng dữ liệu ngày, vấn đề là độ đúng phiên chứ không phải độ tươi.
- Ảnh chụp màn hình lưu trên máy AuditorBot, không commit vào repo.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
