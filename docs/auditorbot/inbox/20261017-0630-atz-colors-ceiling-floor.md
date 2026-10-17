# Báo cáo AuditorBot — Màu & trần/sàn A1–A5 (atz.vn vs FireAnt)

- **ID file:** `20261017-0630-atz-colors-ceiling-floor.md` (task `tasks/20261017-0630-colors-ceiling-floor.md`)
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 07:05–07:17 (thứ Bảy, ngoài phiên; dữ liệu phiên 16/10); viết báo cáo 07:19
- **URL đã mở:**
  - atz: `https://atz.vn` → Tổng quan (Chỉ số Việt Nam, Top 20 KL), Realtime → Bảng giá
  - fireant: `https://fireant.vn/thi-truong` (sort %, lọc sàn), `https://fireant.vn/ma-chung-khoan/HII` (trần), `https://fireant.vn/ma-chung-khoan/KOS` (sàn)
- **Auth / ghi chú phiên:** cả hai đã login, không gặp trang đăng nhập. Desktop 1280×800. Chỉ đọc: chỉ sort cột / lọc sàn trên FireAnt, hover header/cell trên atz. Không bấm lưu/chạy/quét.
- **Công cụ:** Grok AuditorBot + computer use + đọc code `main` @ `fe9450e` (chỉ đọc)
- **Quy ước:** `[live]` = thấy trên UI thật; `[code]` = suy ra từ code; `[calc]` = tính lại từ số live. Màu atz = **ước lượng bằng mắt** (grid canvas, không đọc được DOM); màu FireAnt = **đọc inline style từ DOM** (chính xác).

> Bối cảnh: atz là công cụ kỷ luật + tín hiệu, không phải bản sao FireAnt. Không đề xuất đổi hex theo FireAnt.

---

## 1. Tóm tắt

1. **A1–A3 Pass hướng màu [live]:** 30/30 dòng Realtime đúng hướng (22 xanh, 4 đỏ, 4 vàng TC), khớp FireAnt từng mã. Nhưng app đang render **nền trắng (light theme)** trong khi token `COLOR_TOKENS.md` thiết kế cho dark (`BG_PRIMARY #121418`): vàng TC `#FFC107` trên trắng chỉ **1.63:1**, xanh `#00C853` 2.24:1, xanh dương sàn `#29B6F6` 2.30:1 → khó đọc (P1).
2. **A4–A5 BLOCKED trên atz [live]:** caption `trần 0 · sàn 0 · limit API 30/30`. Phiên 16/10 FireAnt có ≥6 mã trần và ≥5 mã sàn (HII, VDP, HMR, PCE, TBR, MNB / KOS, PMG, NDX, VNY, HVA) nhưng **không mã nào nằm trong 30 mã atz ingest** → với rổ 30 mã bluechip, tím/xanh dương gần như không bao giờ được kiểm thật. Thiếu SP (rổ mã cố định), không phải giới hạn Streamlit.
3. **P1 [code+calc] fallback trần/sàn không làm tròn bước giá:** `price_action.limit_prices()` = TC×(1±7%) không làm tròn tick. Tính lại với 30 TC thật: nếu API thiếu field, **18/30 mã sẽ không được tô tím khi chạm trần** (và 18/30 không tô xanh dương khi chạm sàn), vd ACB TC 20,600 → ước lượng 22,042 vs trần thật 22,000. Hiện chưa ảnh hưởng vì API trả 30/30, nhưng mã mới/IPO/thiếu field sẽ sai.
4. **P1 [code, hunch] trần/sàn chỉ áp ở bảng Realtime:** `price_state()` chỉ được gọi trong `realtime_page.py`; Top 20 KL Tổng quan (có mã ngoài rổ 30 như PVS, HCM, DXG, DIG), thẻ chỉ số và sidebar chỉ tô xanh/đỏ/vàng → mã trần/sàn ở đó sẽ hiện xanh/đỏ.
5. **Nhắc lại từ 0622 (vẫn còn) [live]:** cột Trần/Sàn giá vẫn `22000.000000`; code `main` có `styled.hide(subset=["Sàn","Trần","Sàn giá"])` nhưng UI vẫn hiện → hoặc deploy chưa lên, hoặc `st.dataframe` bỏ qua `Styler.hide` cho cột (hunch, cần Cursor xác minh).

---

## 2. Bảng đối chiếu A1–A5

| ID | Tiêu chí | FireAnt [live, DOM] | atz / VANTIQ | Lệch? | Tag | Loại |
|---|---|---|---|---|---|---|
| A1 | Tăng | `#00BB00` (vd VHM +3.57%) | Xanh lá, 22/30 dòng đúng hướng [live]; token `#00C853` [code]. Trên nền trắng 2.24:1 [calc] | Hướng: Không | Pass (hướng) / P1 (tương phản nền trắng) | Thiếu SP (theme) |
| A2 | Giảm | `#BB0000` (vd VIC −1.38%) | Đỏ cam, 4/30 (GAS, MBB, PLX, VIC) [live]; token `#FF3D00` 3.55:1 trên trắng [calc] | Không | Pass | — |
| A3 | Tham chiếu | `#EEBB00` (vd HDB 0.00%) | Vàng, 4/30 (ACB, HDB, SAB, STB) [live]; token `#FFC107` **1.63:1** trên trắng [calc] | Hướng: Không | Pass (hướng) / **P1** (khó đọc) | Thiếu SP (theme) |
| A4 | Trần | `#FF00FF` magenta trên +/- và %; ô Giá không tô; trang mã: Cao 9.51 magenta (HII) | Không có mã trần trong rổ 30 [live]. Token `#AB47BC` + bold trên Giá/+/-/% [code] | Không quan sát được trên atz | **BLOCKED** (rổ mã) | Thiếu SP |
| A5 | Sàn | `#00DFDF` cyan trên +/- và %; trang mã KOS: Mở/Thấp/Cao 7.22 cyan | Không có mã sàn trong rổ 30 [live]. Token `#29B6F6` + bold [code] | Không quan sát được trên atz | **BLOCKED** (rổ mã) | Thiếu SP |
| A4/5-a | Nguồn giá trần/sàn | Không hiện Trần/Sàn trên trang mã; tô theo giá = biên (CFV UPCOM +14.36% xanh, MNB +14.80% tím) | Field API `ceiling_price/floor_price` 30/30; 10 mã soát (ACB…HPG) khớp TC±7% làm tròn tick [live+calc] | Không | Pass | — |
| A4/5-b | Fallback khi thiếu field | — | TC×1.07 / ×0.93 không làm tròn tick, `tol = max(TC×0.05%, 1đ)` → 18/30 trượt trần, 18/30 trượt sàn [code+calc] | Có (tiềm ẩn) | **P1** | Thiếu SP |
| A4/5-c | Phạm vi áp trần/sàn | Áp cả list `/thi-truong` và trang mã | Chỉ bảng Realtime; Top 20 KL / thẻ chỉ số / sidebar dùng màu theo Δ [code] | Có | P1 | Thiếu SP |
| — | Format Trần/Sàn giá | — | `22000.000000`, `40900.000000` [live] | Có | P1 (đã báo 0622) | Thiếu SP |
| — | Tooltip/legend | Không | Không tooltip khi hover header/ô; legend chỉ ở caption `tím=trần · xanh dương=sàn · xanh/đỏ/vàng=Δ` [live] | — | P2 | Giới hạn Streamlit (`st.dataframe` không tooltip theo ô) |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Bảng giá [live]:** caption `Cập nhật lúc 07:08:04 · tự cập nhật mỗi 30s · quote mới nhất 07:07:30 · hiện 30/30 mã · trần 0 · sàn 0 · limit API 30/30 · spark cache 30 · tím=trần · xanh dương=sàn · xanh/đỏ/vàng=Δ`. 15 cột hiện đủ (toggle «Chỉ hiện cột chính» tắt). Màu: vàng ACB/HDB/SAB/STB (+0); đỏ GAS −0.13, MBB −0.25, PLX −1.41, VIC −1.38; còn lại xanh. Giá/+/-/TC khớp FireAnt.
- **Trần/Sàn giá API vs tính lại [live+calc]:** ACB 22,000/19,200; BCM 40,900/35,600; BID 35,500/30,900; BVH 76,300/66,500; CTG 31,850/27,750; FPT 62,000/54,000; GAS 81,500/70,900; GVR 33,050/28,750; HDB 24,350/21,250; HPG 22,200/19,300 — cả 10 = TC×(1±7%) làm tròn tick HOSE (10/50/100đ).
- **Nền trắng [live]:** screenshot desktop cho thấy nền app trắng, bảng nền trắng; thẻ chỉ số nền tối. Token màu thiết kế cho dark mode (`TEXT_PRIMARY #FFFFFF`). Hunch: theme Streamlit theo hệ điều hành/trình duyệt, cần Cursor xác minh `.streamlit/config.toml` (không đọc file cấu hình server).
- **[code] `ui/price_action.py`:** `limit_prices(ref)` trả `ref*(1+pct), ref*(1-pct)` không làm tròn; `price_state()` dùng `tol = max(tc*0.0005, 1.0)`. Ví dụ ACB: px 22,000 < 22,042 − 10.3 → trả `up` thay `ceiling`.
- **[code, hunch]** `realtime_page.py:183-189` truyền `ceiling=row.get("Trần")`. Khi một số dòng thiếu field, cột pandas sẽ là `NaN` chứ không phải `None` → `ceiling is not None` đúng → `ceil = NaN` → không bao giờ ra `ceiling`/`floor` và **không rơi vào fallback**; đồng thời `n_api` đếm `is not None` sẽ báo «limit API 30/30» sai. Cần Cursor viết test với 1 dòng thiếu field để xác nhận.
- **[code]** `price_state()` chỉ được gọi ở `ui/realtime_page.py` (và sparkline). `overview_page.py` Top 20 KL, thẻ chỉ số, `sidebar_portfolio.py` tô theo dấu Δ.
- **Tổng quan [live]:** Top 20 KL vẫn lệch phiên như báo cáo 0622 (MBB +2.84% xanh vs Realtime −0.25% đỏ; VHM −3.44% đỏ vs +3.57% xanh; STB −2.79% vs 0.00%) và thẻ VNIndex −0.85% vs Realtime +0.45%. Không nhắc lại chi tiết; xem `20261017-0622-atz-f1-acceptance-baseline.md`.
- **Time & Sales [live]:** dropdown «Chi tiết mã (Time & Sales / cảnh báo)» trống «—». Ngoài phạm vi task này.

### 3.2 fireant.vn

- **Màu (inline style DOM) [live]:** tăng `rgb(0,187,0)`; giảm `rgb(187,0,0)`; TC `rgb(238,187,0)`; trần `rgb(255,0,255)`; sàn `rgb(0,223,223)`. Trên list `/thi-truong`, màu trần/sàn áp cho +/- và %, ô Giá không tô.
- **Mã trần phiên 16/10 [live]:** HOSE HII 9.51 +6.97% (TC 8.89), VDP 32.30 +6.95%; HNX HMR 8.80 +10.00%, PCE 17.70 +9.94%; UPCOM TBR 6.90 +15.00%, MNB 28.70 +14.80%.
- **Mã sàn [live]:** HOSE KOS 7.22 −6.96% (TC 7.76), PMG 5.82 −6.88%; HNX NDX 4.80 −9.43%; UPCOM VNY 5.10 −15.00%, HVA 3.40 −15.00%.
- **Tô theo giá = biên, không theo ngưỡng %** [live]: CFV UPCOM +14.36% xanh, MNB +14.80% tím (MNB đúng bằng trần sau làm tròn).
- **Trang mã HII/KOS [live]:** không hiển thị nhãn Trần/Sàn; TC/Mở vàng; giá biên tô màu trần/sàn ở dải «Vùng giá hôm nay». HII «Cập nhật lúc 15:30:11», KOS «14:46:10».

---

## 4. Đề xuất cho Cursor (tối đa 5, đo được)

1. `[P1]` Fallback trần/sàn làm tròn theo bước giá từng sàn (HOSE 10/50/100đ; HNX/UPCOM 100đ) — trần làm tròn xuống, sàn làm tròn lên. **Done khi:** unit test với 30 TC ở bảng 3.1 (ACB 20,600 → 22,000/19,200; MBB 19,900 → 21,250/18,550; VIC 218,000 → 233,200/202,800; KOS 7,760 → sàn 7,220) cho `price_state()` = `ceiling`/`floor` khi **không truyền** field API.
2. `[P1]` Xử lý `NaN` như thiếu field trong `price_state()` và `n_api`. **Done khi:** test frame có 1 dòng `Trần=NaN` ở giá trần → vẫn ra `ceiling` qua fallback, caption báo `limit API 29/30`.
3. `[P1]` Có cách kiểm A4/A5 thật: cho thêm mã ngoài rổ 30 vào board (watchlist/env danh sách mã) hoặc fixture demo. **Done khi:** trong phiên có mã trần (vd HII/HMR/TBR kiểu 16/10), board atz hiện ≥1 dòng tím và caption `trần ≥1`.
4. `[P1]` Tương phản màu trên nền trắng: ép dark theme cho app hoặc dùng bộ token tối hơn cho light (giữ hướng màu). **Done khi:** trên `https://atz.vn` desktop mặc định, chữ TC/tăng/sàn đạt ≥3:1 với nền bảng (hiện 1.63 / 2.24 / 2.30).
5. `[P1]` Áp `price_state()` (tím/xanh dương) cho Top 20 KL Tổng quan và sidebar, đồng thời sửa ẩn/format cột Trần/Sàn giá (dùng `column_config`/`column_order` thay `Styler.hide` nếu đó là nguyên nhân). **Done khi:** mã chạm trần trong Top 20 hiện tím; Bảng giá không còn ô dạng `22000.000000`.

(P2: tooltip legend màu theo ô — giới hạn `st.dataframe`; dùng caption/legend là đủ.)

---

## 5. Việc không nên làm

- Đừng đổi hex sang màu FireAnt (`#FF00FF`, `#00DFDF`, `#00BB00`…); chỉ cần đủ tương phản với nền thực tế.
- Đừng tô trần/sàn theo ngưỡng % (vd ≥6.9%) — FireAnt và quy chế dùng giá = trần/sàn làm tròn; UPCOM +14.36% vẫn là xanh.
- Đừng kết luận A4/A5 Pass/Fail trên atz khi rổ mã chưa có mã chạm biên.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
