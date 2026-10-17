# Báo cáo AuditorBot — Sidebar retest sau deploy (C1–C3, E1–E2)

- **ID file:** `20261017-0700-atz-sidebar-retest.md` (task `tasks/20261017-0700-sidebar-retest.md`)
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 07:29–07:34 (thứ Bảy, ngoài phiên; dữ liệu phiên 16/10); viết báo cáo 07:36
- **Phụ thuộc:** VPSbot outbox `20261017-0622-sidebar-live-quote-DONE.md` = **DONE, deploy yes** (HEAD `0816526`, `vnstocks` recreated 2026-10-16T23:35Z). Đã kiểm `git log 0816526..fe9450e`: không có thay đổi ở `sidebar_portfolio.py`, `live_quotes.py`, `realtime_page.py`, `price_action.py` → bản live = code `main` @ `fe9450e` cho các file này.
- **URL đã mở:**
  - atz: `https://atz.vn` → sidebar «Tổng quan vị thế của bạn», Realtime → Bảng giá (ô «Tìm mã nhanh»)
  - fireant: `https://fireant.vn/ma-chung-khoan/TPB`, `https://fireant.vn/ma-chung-khoan/POW`
- **Auth / ghi chú phiên:** cả hai đã login, không gặp trang đăng nhập. Desktop 1280×800. Chỉ đọc: gõ/xoá filter mã, mở expander «Sổ vốn» (không bấm «Lưu sổ vốn»).
- **Công cụ:** Grok AuditorBot + computer use + đọc code `main` @ `fe9450e` (chỉ đọc)
- **Quy ước:** `[live]` = thấy trên UI thật; `[code]` = suy ra từ code; `[calc]` = tính lại từ số live.

---

## 1. Tóm tắt

1. **Không regression sau deploy [live]:** C1, C2, E1, E2 Pass. Sidebar giống hệt baseline 06:50 (vốn 100,000,000 · GTCK 49,921,721 · NAV 99,921,721, badge `-78279`; TPB 11.80→12.00, POW 12.45→12.20). Màu board 22 xanh / 4 đỏ / 4 vàng / 0 trần / 0 sàn, khớp từng mã với baseline; không banner lỗi.
2. **E1 Pass cho TPB [live]:** sidebar 12.00 = board 12,000 (+250, +2.13%, TC 11,750) = FireAnt 12.00 (+0.25, +2.13%, TC 11.75). Đơn vị nghìn đồng ↔ VND đúng (xác nhận fix `_price_to_thousands`).
3. **P1 [live+code] Mã đang nắm giữ ngoài rổ 30 không có giá realtime:** POW không có trên board («Không có mã khớp «POW».») và là Redis miss → sidebar dùng OHLCV đóng cửa (`Redis 1/2`). Hôm nay đúng (12.20 = FireAnt), nhưng **trong phiên POW sẽ đứng giá đóng cửa hôm trước** mà UI không báo mã nào bị fallback. Thiếu SP (rổ ingest cố định), không phải giới hạn Streamlit.
4. **C3 không kết luận được [live+calc]:** cả 2 dòng «—». Theo `position_alert()` [code], TPB +1.69%, POW −2.01% so giá mua → chưa chạm mốc 5/8/10%; vùng hỗ trợ/kháng cự trên desk không hiện ở sidebar nên không biết «—» là «không gần vùng» hay «chưa nhập vùng». UX P1 nhẹ.
5. **Không có cảnh báo stale [code]:** `live_quotes.py` không đọc timestamp quote (VPSbot `0630` cũng ghi «Quote stale: Skipped») → ngoài giờ / ingestion chết, sidebar vẫn ghi `Redis` như giá sống.

---

## 2. Bảng đối chiếu (Pass/Fail theo `docs/bots/ACCEPTANCE_TESTS.md`)

| ID | Tiêu chí | FireAnt [live] | atz / VANTIQ | Kết quả | Tag | Loại |
|---|---|---|---|---|---|---|
| C1 | Khối «Tổng quan vị thế» có vốn/NAV/mã | — (không có tính năng tương đương) | Tổng vốn 100,000,000; GTCK 49,921,721; Tiền mặt 50,000,000; NAV 99,921,721 (badge đỏ `-78279`); TPB, POW [live] | **Pass** | — | — |
| C2 | Giá HT khác giá cũ khi thị trường sống / Notes phiên nghỉ | TPB 12.00, POW 12.20 (cập nhật 15:30 16/10) | TPB 12.00 (Redis), POW 12.20 (OHLCV); caption «Ngoài phiên · Giờ HN 07:29» + «Giá HT: Redis 1/2» [live] | **Pass (phiên nghỉ)** — không kiểm được biến động trong phiên | P1 (nhãn nguồn từng mã) | Thiếu SP |
| C3 | Cảnh báo gần HT/KC / ±% | — | Cả 2 dòng «—»; TPB +1.69%, POW −2.01% [calc] < mốc 5% [code `ALERT_BANDS`] | **Không kết luận** (chưa có điều kiện kích hoạt) | P1 | Thiếu SP (không thấy vùng HT/KC) |
| E1 | Giá sidebar khớp hướng board cùng mã | TPB +2.13% | TPB sidebar 12.00 = board 12,000 xanh +2.13% [live]; POW không có trên board | **Pass** (TPB) / **N/A** (POW) | P1 (POW) | Thiếu SP (rổ ingest) |
| E2 | Không regression màu A1–A5 | — | 22 xanh, 4 đỏ (GAS, MBB, PLX, VIC), 4 vàng (ACB, HDB, SAB, STB), tím 0, xanh dương 0 — giống hệt baseline [live] | **Pass** (A4/A5 vẫn BLOCKED như `0630-colors`) | — | — |
| — | Màu lãi/lỗ trong sidebar | — | Giá HT chữ đen; bar chart lãi/lỗ cùng một màu xanh dương cho cả lãi (TPB ≈ +430k) và lỗ (POW ≈ −500k) [live, đọc mắt] | Có | P2 | Một phần giới hạn Streamlit (`st.bar_chart` không tô theo dấu dễ; có thể dùng Altair/`column_config`) |
| — | Trạng thái ngoài giờ trên board | Trang mã ghi «Cập nhật lúc 15:30:24» | Board ghi «quote mới nhất 07:33:35», tự cập nhật 30s dù giá = đóng cửa 16/10 [live] | Có | P2 (đã báo `0622`) | Thiếu SP |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Sidebar [live, 07:29–07:30]:** «Ngoài phiên · Giờ HN 07:29 17/10/2026». Bảng «Vị thế hiện tại» chỉ 4 cột: Mã | Giá mua | Giá HT | Cảnh báo (không KL, không %). TPB 11.80 | 12.00 | —; POW 12.45 | 12.20 | —. Caption «Giá HT: Redis 1/2 (nghìn đồng). Tham chiếu: https://rtboard.hsx.vn/». Expander «Sổ vốn»: Vốn rót lần đầu 100,000,000.00; bổ sung 0.00; rút 0.00.
- **NAV [calc]:** 100,000,000 − 78,279 = 99,921,721 ✓; GTCK 49,921,721 = 2 × 25,000,000 phân bổ × (giá HT / giá mua): 25M×12.00/11.80 + 25M×12.20/12.45 = 25,423,729 + 24,497,992 = 49,921,721 ✓ (khớp `desk_position_rows` [code]).
- **Bảng giá [live]:** caption «Cập nhật lúc 07:33:47 · tự cập nhật mỗi 30s · quote mới nhất 07:33:35 · hiện 30/30 mã · trần 0 · sàn 0 · limit API 30/30 · spark cache 30 · tím=trần · xanh dương=sàn · xanh/đỏ/vàng=Δ». Filter «Tìm mã nhanh»: `TPB` → 1 dòng; `POW` → «Không có mã khớp «POW».»
- **Màu E2 [live]:** đỏ GAS 76,100 −0.13%, MBB 19,850 −0.25%, PLX 35,050 −1.41%, VIC 215,000 −1.38%; vàng ACB 20,600, HDB 22,800, SAB 43,000, STB 62,800 (Δ 0); xanh vd CTG +2.68%, BID +2.26%, VHM +3.57%. Không banner lỗi / traceback / chunk error.
- **Vẫn còn từ báo cáo trước [live]:** cột Trần/Sàn giá hiển thị `22000.000000`, `19200.000000` (xem `0630-colors`, đề xuất 5).
- **[code] `sidebar_portfolio.py`:** `price_source` (`redis`/`ohlcv`) được tính từng dòng nhưng chỉ dùng để đếm `Redis x/y`, không hiện trong bảng. `position_alert()` chỉ ra text khi |giá − HT/KC| ≤ 2% hoặc chạm ±5/8/10% so giá mua; ngược lại «—». Giá HT không đi qua `price_state()` nên không tô màu.
- **[code] `live_quotes.py`:** chỉ đọc `data["price"]`, không kiểm thời gian quote; `_price_to_thousands` dùng ngưỡng `>= 1000` (VPSbot đã ghi rủi ro).

### 3.2 fireant.vn

- **TPB [live]:** 12.00, +0.25 / +2.13%, TC 11.75, Mở 11.85, Thấp–Cao 11.75–12.25, «Cập nhật lúc 15:30:24 | Việt Nam (GMT+7)». Khớp board atz cả giá, Δ, Δ%, TC.
- **POW [live]:** 12.20, 0.00 / 0.00%, TC 12.20, Mở 12.30, Thấp–Cao 12.10–12.35, «Cập nhật lúc 15:30:18». Khớp giá OHLCV sidebar atz.
- FireAnt không có khối vị thế/NAV tương đương trên trang mã → đối chiếu chỉ ở mức giá.

---

## 4. Đề xuất cho Cursor (tối đa 5, đo được)

1. `[P1]` Mã đang nắm giữ (desk) luôn có quote realtime: tự thêm mã desk vào danh sách ingest/board (hoặc quote on-demand cho mã desk). **Done khi:** trong phiên, POW có key `quote:POW` trong Redis, caption sidebar `Redis 2/2`, và filter board `POW` ra 1 dòng.
2. `[P1]` Hiện nguồn giá từng mã trong sidebar (cột nhỏ hoặc hậu tố, vd `12.20 · OHLCV`). **Done khi:** với POW Redis miss, dòng POW có nhãn «OHLCV»/«đóng cửa»; TPB có «live».
3. `[P1]` Đánh dấu quote stale: so timestamp quote với giờ hiện tại/phiên; quá ngưỡng (vd >5 phút trong phiên, hoặc ngoài phiên) thì ghi «đóng cửa 16/10» thay vì coi như live. **Done khi:** test với quote cũ 10 phút trong phiên → nguồn `stale`; ngoài giờ sidebar không ghi Redis như giá sống.
4. `[P1]` C3 rõ nghĩa: phân biệt «chưa nhập HT/KC» với «không gần vùng», và hiện % lãi/lỗ so giá mua. **Done khi:** dòng không có vùng trên desk ghi «Chưa có HT/KC»; dòng TPB hiện `+1.7%` (xanh), POW `−2.0%` (đỏ).
5. `[P2]` Tô màu lãi/lỗ trong sidebar (Giá HT theo `price_state()` hoặc theo dấu so giá mua; bar chart xanh/đỏ theo dấu). **Done khi:** bar TPB xanh, POW đỏ; Giá HT POW đỏ.

---

## 5. Việc không nên làm

- Đừng bê bảng danh mục FireAnt vào sidebar; mục tiêu là kỷ luật (vốn 1/4, mốc cảnh báo), chỉ cần giá đúng + nguồn rõ.
- Đừng tăng tần suất làm tươi sidebar để «giả realtime» cho mã ngoài rổ — sửa nguồn quote (đề xuất 1) thay vì refresh.
- Ảnh chụp màn hình lưu trên máy AuditorBot, không commit vào repo.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
