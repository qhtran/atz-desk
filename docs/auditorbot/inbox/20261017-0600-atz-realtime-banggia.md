# Báo cáo AuditorBot — Bảng giá realtime (màu, trần/sàn, flash, tìm mã)

- **ID file:** `20261017-0600-atz-realtime-banggia.md`
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 05:44–05:47 (ngoài phiên, giá đứng yên); viết báo cáo lúc ~06:00
- **URL đã mở:**
  - atz: `https://atz.vn` → Realtime → Bảng giá
  - fireant: `https://fireant.vn/thi-truong`, `https://fireant.vn/ma-chung-khoan/VHM`, `https://fireant.vn/bang-gia` (404)
- **Auth / ghi chú phiên:** atz đã login (desktop). Quan sát **ngoài giờ giao dịch** nên flash/độ trễ chưa đo được.
- **Công cụ:** Grok AuditorBot + computer use + đọc code `main` (chỉ đọc)
- **Quy ước:** `[live]` = thấy trên UI thật; `[code]` = chỉ suy ra từ code, chưa thấy trên UI.

> Bối cảnh: atz là công cụ **kỷ luật + tín hiệu** (lọc, cảnh báo, vị thế), không phải bản sao FireAnt. Đối chiếu dưới đây chỉ để chọn phần đáng học, không nhằm «làm giống FireAnt».

---

## 1. Tóm tắt

1. **P0 [live]:** Trang hiện lỗi đỏ `TypeError: Failed to fetch dynamically imported module … TextInput.CaHPfYwH.js`. Khả năng cao là chunk frontend cũ còn cache sau khi deploy, và lỗi này có thể làm hỏng ô tìm mã.
2. **P1 [live]:** Trần/Sàn hiển thị dạng `22000.000000` (lỗi định dạng). Ngoài giờ giao dịch mà mọi dòng vẫn ghi `live`.
3. **P1 [code]:** Trần/sàn ước lượng (khi API thiếu field) không làm tròn theo bước giá, và không kiểm tra TC cũ. Hiện chưa gây lỗi vì caption ghi `limit API 30/30`, nghĩa là cả 30 mã đang dùng giá thật từ API.
4. Màu xanh/đỏ/vàng đúng. Chưa thấy màu tím/xanh dương vì `trần 0 · sàn 0`. Board chỉ có 30 mã VN30, không có giá mua/bán, dư mua/bán, khối ngoại.
5. **BLOCKED:** flash và độ trễ phải đo trong phiên. Hover dòng và click dòng để mở chi tiết bị giới hạn bởi Streamlit.

---

## 2. Bảng đối chiếu

| Tiêu chí | FireAnt | atz / VANTIQ | Lệch? | Tag | Loại |
|---|---|---|---|---|---|
| Lỗi frontend | Không thấy | Lỗi đỏ dynamic import `TextInput.CaHPfYwH.js` [live] | Có | P0 | Thiếu SP (deploy/cache) |
| Màu tăng/giảm/TC | Xanh/đỏ/vàng | Xanh/đỏ/vàng đúng [live] | Không | — | — |
| Màu trần/sàn | Tím/xanh lam | Có token tím `#AB47BC` và xanh dương `#29B6F6` [code]. Chưa thấy trên UI vì trần 0 · sàn 0 [live] | Chưa kiểm được | — | — |
| Cột Trần/TC/Sàn | Không có trên `/thi-truong`. Trang mã có | Có cột, nhưng hiện `22000.000000` [live] | Có | P1 | Thiếu SP (format) |
| Trạng thái dòng ngoài giờ | — | Mọi dòng `live`, trong khi caption ghi «Ngoài giờ giao dịch» [live] | Có | P1 | Thiếu SP |
| Trần/sàn ước lượng | — | `ref*(1±%)` không làm tròn bước giá, `tol` khoảng 0.05% (`src/atz/ui/price_action.py:21-55`) [code] | Có | P1 | Thiếu SP |
| TC cũ / GDKHQ / IPO | — | Không kiểm tra ngày của TC. TC thiếu thì hiện vàng. Không có biên độ ±20/30/40% cho ngày đầu (`src/atz/ingestion/normalizer.py:59-62`) [code] | Có | P1 | Thiếu SP |
| Số mã | List 20/50/100 dòng, tab theo sàn | 30 mã VN30 [live] | Có | P2 | Thiếu SP |
| Giá mua/bán 3 mức, dư mua/bán, khối ngoại | Trang mã → tab Sổ lệnh (3 mức giá + danh sách Khớp), tab Mức giá | Không có [live] | Có | P2 | Thiếu SP (dữ liệu) |
| Tìm mã | Ô tìm trên header có dropdown | Ô tìm lọc bảng [code]. Lỗi chunk TextInput [live]. Tìm (find) trong grid chỉ highlight, không lọc [live] | Có | P0/P1 | Thiếu SP + Giới hạn Streamlit |
| Click dòng → chi tiết | Click mã mở trang mã | Chỉ qua selectbox, click dòng không ra gì [live] | Có | P2 | Giới hạn Streamlit (một phần: có `on_select`) |
| Hover dòng | Có highlight | Không có [live] | Có | BLOCKED | Giới hạn Streamlit |
| Time & Sales | Danh sách Khớp | Placeholder, link sang rtboard.hsx.vn [live] | Có | P2 | Thiếu SP |
| Flash khi giá đổi | Có (trong phiên) | Có code CSS animation (`src/atz/ui/theme_tokens.py:131-134`) [code]. Chưa đo trên UI | ? | BLOCKED | Có thể là giới hạn Streamlit |
| Chu kỳ / độ trễ | Gần realtime | Caption ngoài giờ ghi `tự cập nhật mỗi 30s` [live]. Trong phiên là 5s theo config `config/ui_realtime.yaml:8` [code] (docstring vẫn ghi 3s) | ? | BLOCKED | Cần đo trong phiên |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Lỗi chunk [live]:** banner đỏ báo `TypeError: Failed to fetch dynamically imported module … TextInput.CaHPfYwH.js`. Lỗi kiểu này thường do trình duyệt hoặc proxy giữ `index.html` cũ, trỏ tới chunk đã bị xoá sau khi rebuild image Streamlit. Cần kiểm tra lại header cache của nginx với `/static/` và `index.html`, rồi hard reload.
- **Bảng [live]:** 30 dòng VN30, 15 cột, trong đó cột Trần và Sàn đang hiện. Giá trị trần/sàn hiện `22000.000000`, tức là chưa được format như các cột giá khác. Theo code, các cột này bị loại khỏi `subset` format (`src/atz/ui/realtime_page.py:257`) và lẽ ra bị ẩn qua `styled.hide` (`:260-262`). Việc chúng vẫn hiện cho thấy hide không có tác dụng trên `st.dataframe`, hoặc bản đang deploy khác code `main` [code + live].
- **Caption [live]:** `limit API 30/30`, `trần 0 · sàn 0`, `tự cập nhật mỗi 30s`. Session ghi «Ngoài giờ giao dịch».
- **Trạng thái [live]:** mọi dòng `live`, dù ngoài phiên. Code chỉ đánh dấu stale khi quote cũ hơn 120s hoặc bị gắn cờ (`src/atz/ui_realtime/data.py:216-233`). Ngoài giờ ingestion vẫn poll mỗi 60s nên quote luôn «mới» [code].
- **Chi tiết mã [live]:** phải chọn mã qua selectbox. Click dòng không mở gì, không có hover. Panel Time & Sales chỉ là placeholder kèm nút mở rtboard.hsx.vn.
- **Tìm [live]:** chức năng find tích hợp của grid chỉ highlight, không lọc. Ô «Tìm mã nhanh» lọc theo substring theo code (`src/atz/ui_realtime/board_view.py:10-16`), nhưng có thể đang bị lỗi chunk TextInput ở trên.

### 3.2 fireant.vn

- `/bang-gia` trả 404: hiện không còn bảng giá cổ điển kiểu sàn.
- `/thi-truong`: danh sách 20/50/100 dòng, có tab theo sàn, hover highlight dòng. Không có cột Trần/TC/Sàn.
- `/ma-chung-khoan/VHM`: tab **Sổ lệnh** có 3 mức giá mua/bán và danh sách Khớp, thêm tab **Mức giá**. Header có ô tìm kèm dropdown gợi ý.
- Flash và độ trễ của FireAnt chưa đo vì đang ngoài phiên.

---

## 4. Đề xuất cho Cursor (tối đa 5)

1. `[P0]` Sửa lỗi dynamic import `TextInput.*.js` (header cache cho `index.html` và `/static`, hard reload sau deploy). **Done khi:** sau một lần deploy mới, reload trang không còn banner TypeError, và ô tìm mã lọc được bảng.
2. `[P1]` Format cột Trần/Sàn giống cột giá (`{:,.0f}`) hoặc ẩn đúng cách (`column_config` hoặc bỏ cột khỏi frame). **Done khi:** không còn ô nào dạng `22000.000000`.
3. `[P1]` Ngoài giờ giao dịch, hiển thị trạng thái `đóng cửa`/`cuối phiên` thay cho `live`. **Done khi:** lúc 05:45 không có dòng nào ghi `live`.
4. `[P1][code]` Làm tròn trần/sàn ước lượng theo bước giá (trần làm tròn xuống, sàn làm tròn lên) và đặt `tol` bằng 1 bước giá. **Done khi:** có unit test cho HOSE ở 3 vùng giá, HNX và UPCOM.
5. `[P1][code]` Kiểm tra TC còn mới: ngày của TC phải bằng ngày giao dịch. TC thiếu hoặc cũ thì trạng thái `unknown` (xám), không tô vàng, không dùng giá ước lượng. **Done khi:** có test cho ca TC thiếu và ca GDKHQ.

(P2 để sau: chọn dòng bằng `on_select` để mở chi tiết, Time & Sales từ intraday, giá mua/bán 3 mức.)

---

## 5. Việc không nên làm

- Đừng cố làm hover dòng hay phím tắt toàn cục bằng hack CSS/JS trên `st.dataframe` (BLOCKED). Nếu thật sự cần thì đánh giá phương án custom component.
- Đừng kết luận về flash hay độ trễ khi chưa đo trong phiên 09:15–11:30 hoặc 13:00–14:30.
- Đừng biến atz thành bản sao bảng giá FireAnt. Ưu tiên tính đúng của trần/sàn/TC phục vụ tín hiệu.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
