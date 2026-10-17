# Báo cáo AuditorBot — Retest sau UX wave (pin / workspace / bảng)

- **ID file:** `20261017-1530-atz-post-ux-wave-retest.md` (task `tasks/20261017-1530-post-ux-wave-retest.md`)
- **Ngày giờ (Asia/Ho_Chi_Minh):** quan sát live 2026-10-17 15:39–15:54 (thứ Bảy, ngoài phiên; dữ liệu phiên 16/10); viết báo cáo ~15:54
- **HEAD quan sát:** `main` @ `22154f7` (ancestor `d19ef30` filter prefs seed + pin strip + trading workspace — **có**)
- **URL đã mở:**
  - atz: `https://atz.vn` → Tổng quan (Top 20 KL, chỉ số), Realtime → Bảng giá (search TPB/POW, khối ghim), **Không gian Trading**, Tin tức/RSS
  - fireant: `https://fireant.vn/thi-truong` (tab Thanh khoản), `/ma-chung-khoan/{VHM,STB,MBB,TPB,POW,VIC,GAS}`, VNINDEX trên `/thi-truong`
- **Auth / ghi chú phiên:** cả hai đã login, không gặp trang đăng nhập. Desktop 1280×800. Chỉ đọc: chuyển tab, gõ/xoá filter, mở dropdown Chi tiết mã rồi Esc; **không** Lưu / Ghim / Quét.
- **Công cụ:** Grok AuditorBot + computer use
- **Quy ước:** `[live]` = UI thật; `[code]` = suy từ code `main`; `[calc]` = tính lại. Ảnh chụp lưu trên máy AuditorBot, **không** commit binary.

---

## 1. Tóm tắt

1. **UX wave đã lên production [live]:** khối ghim Realtime (trạng thái trống «Chưa ghim mã nào.»), tab **Không gian Trading** (form Vốn·Risk·Filter defaults + pin text, không bấm Lưu), bảng Realtime mật độ cao 30 mã + search Enter-to-apply. RSS/Tin tức **không** lộ HTML thô (Pass so với brief overnight).
2. **P0 [live] — Tổng quan Top KL / giá cổ phiếu lệch phiên so FireAnt + Realtime:** cùng mã, Overview «Giá» = cột **TC** của Realtime/FireAnt, Δ và màu ngược hướng. VHM Overview 58.90 đỏ −3.44% vs FireAnt/Realtime 61.00 xanh +3.57%; STB Overview −2.79% đỏ vs FireAnt/Realtime **0.00% vàng**; MBB Overview +2.84% vs FireAnt/Realtime −0.25%. Sidebar Giá HT (TPB 12.00) khớp Realtime/FireAnt → lỗi nằm ở nguồn OHLCV/Top KL, không ở Redis quote.
3. **P0 [live] — VNINDEX mâu thuẫn:** Overview «TC 1,719.42 · Đóng 1,704.87 · −0.85%» đỏ; Realtime + FireAnt **1,705.91 +7.56 / +0.45%** xanh (TC FireAnt 1,698.35). Realtime đúng; Overview sai.
4. **P1 [live]:** Trần/Sàn raw float (`12550.000000`); nhãn «live» ngoài phiên; zebra tối + chữ xanh/đỏ khó đọc; bar PnL một màu xanh dương cho cả lãi/lỗ; VNINDEX trong Top 20 (nhãn cắt «VNINDE»); POW nắm giữ nhưng không có trên board 30 mã («Không có mã khớp «POW».»); 8× 502 `/_stcore/health` (app vẫn render).
5. **Flash tick [live]:** ngoài phiên giá không đổi qua ≥3 chu kỳ 30s → **không đánh giá** được flash. Pin flow không test (tránh đổi state).

---

## 2. Bảng đối chiếu

| Tiêu chí | FireAnt [live] | atz / VANTIQ | Lệch? | Tag | Loại |
|----------|----------------|--------------|-------|-----|------|
| Màu tăng/giảm/TC board | VHM +3.57% xanh; MBB −0.25% đỏ; STB/POW 0% vàng | Realtime 22 xanh / 4 đỏ / 4 vàng / trần 0 / sàn 0; Δ=Giá−TC khớp 30/30 | Không (board) | — | — |
| Giá + Δ cùng mã (VHM) | 61.00 +2.10 +3.57% TC 58.90 | Realtime 61,000 +3.57%; **Overview 58.90 −3.44%** | Có (Overview) | **P0** | Thiếu SP (OHLCV/Top KL) |
| STB | 62.80 0.00% | Realtime 62,800 vàng; Overview 62.80 **−2.79% đỏ** | Có | **P0** | Thiếu SP |
| MBB | 19.85 −0.25% KL 10,919,400 | Realtime 19,850 −0.25%; Overview 19.90 **+2.84%** KL 32,621,600 | Có | **P0** | Thiếu SP |
| TPB | 12.00 +2.13% KL 18,806,500 | Realtime 12,000 +2.13%; Overview 11.75 +0.43%; sidebar HT 12.00 | Overview lệch | **P0** | Thiếu SP |
| POW | 12.20 0.00% KL 4,843,200 | Sidebar HT 12.20; Overview 12.20 **−2.01%** KL 11,371,900; board **không có mã** | Có | **P0** / P1 | Thiếu SP (OHLCV + rổ ingest) |
| VNINDEX | 1705.91 +7.56 +0.45% TC 1698.35 | Realtime khớp; Overview −0.85% / đóng 1704.87 | Có | **P0** | Thiếu SP (2 nguồn chỉ số) |
| Top KL / Thanh khoản | SHB, VIX, HDB, TPB, NVL… | Top 20: MBB, POW, STB, HCM, DXG… (không khớp thứ tự FireAnt) | Có | P1 | Thiếu SP (metric/ngày) |
| Pinned strip | (watchlist sao — khác SP) | Có UI «Chi tiết mã» + «Chưa ghim»; heading «Đang ghim» **không** hiện khi empty | Một phần | P2 | Thiếu SP (copy empty) |
| Không gian Trading | — | Tab có: Vốn 100M, Risk 2%, ROE 12, KL 100k, RS −100, top_n 20, RSI 30/70, MACD 12/26/9, pin rỗng | Không (smoke) | — | — |
| RSS HTML thô | — | Bản tin 16/10 markdown; RSS 50 tin, **không** lộ thẻ thô | Không | — | — |
| Trần/Sàn format | không hiện trên trang mã | `22000.000000` / `12550.000000` | Có | P1 | Thiếu SP |
| «live» ngoài phiên | cập nhật 15:30 | Mọi dòng Trạng thái `live`; stamp tiến mỗi 30s, giá đứng | Có | P1 | Thiếu SP |
| Zebra + contrast | giá header trắng | Hàng sọc tối + chữ xanh/đỏ khó đọc (chỉ số, screener, POW sidebar) | Có | P1 | Thiếu SP (theme) |
| Bar PnL theo dấu | — | TPB (+) và POW (−) cùng xanh dương (= màu sàn) | Có | P1 | Thiếu SP |
| VNINDEX trong Top 20 CP | không | Có dòng VNINDEX/«VNINDE» 1704.87 −0.85% | Có | P1 | Thiếu SP |
| Flash tick | — | Không đổi giá ngoài phiên → N/A | — | — | — |
| Hover row / T&S | hover yếu; T&S không thấy trên trang mã | Streamlit grid | — | **BLOCKED** / P2 | Giới hạn Streamlit |
| Đơn vị giá | nghìn (61.00) | Overview nghìn; Realtime đồng (61,000) | Có | P2 | Thiếu SP |
| Mobile vs desktop | SPA dày | 1280×800: board 15 cột vừa, grid cần scroll trong; sidebar chữ nhỏ | — | P2 | — |

---

## 3. Phát hiện chi tiết

### 3.1 atz.vn

- **Sidebar [live ~15:39]:** «Ngoài phiên · Giờ HN 15:39 17/10/2026». Vốn 100,000,000 · GTCK 49,921,721 · Tiền mặt 50,000,000 · NAV 99,921,721 · badge đỏ «−78279». TPB 11.80 | 12.00; POW 12.45 | 12.20. Caption «Giá HT: Redis 1/2 (nghìn đồng)». Bar lãi/lỗ **cùng xanh dương** cho cả hai mã.
- **Top 20 KL [live]:** 5 dòng đầu MBB 19.90 · 32,621,600 · +2.84; POW 12.20 · −2.01; STB 62.80 · −2.79; HCM 24.00 · +3.90; DXG 10.25 · +2.50. Sparkline có. Cuối bảng có VNINDEX (nhãn cắt). **Cross-tab:** Overview Giá = Realtime TC cho ≥10 mã chung; hướng Δ ngược Realtime/FireAnt.
- **Realtime [live 15:42–15:46]:** «tự cập nhật mỗi 30s · hiện 30/30 · trần 0 · sàn 0». 22/4/4. Index cards khớp FireAnt (VNINDEX 1,705.91 +0.45%…). Search Enter: TPB → 1/30; POW → «Không có mã khớp «POW».». **Pinned strip:** controls + «Chưa ghim mã nào.»; không thấy heading «Đang ghim» khi empty. Flash: N/A ngoài phiên. Trần/Sàn raw float. Console 8× 502 `/_stcore/health`.
- **Không gian Trading [live]:** subheader + caption SQLite; form Vốn/Risk/Filter/RSI/MACD/pin — defaults như bảng; **không** Lưu.
- **Tin tức [live]:** «Bản tin sáng … 16/10/2026» markdown OK; RSS 10/trang · 50 tin; không regex thẻ HTML thô. Timestamp ISO thô / nguồn `cafef.rss` (P2).
- **[code]** `realtime_page._pinned_live_strip`, `trading_workspace_page.show_trading_workspace`, `render_data_table` 3 variants, `posts_page` + `sanitize_rss_html` — khớp hành vi live.

### 3.2 fireant.vn

- **Thanh khoản [live]:** SHB 49,973,400 +2.40%; VIX; HDB; TPB 18,806,500 +2.13%; NVL… Breadth HOSE 174↑ / 69→ / 120↓.
- **Mã [live đóng cửa ~15:30 16/10]:** VHM 61.00 +3.57% TC 58.90; STB 62.80 0%; MBB 19.85 −0.25% KL 10,919,400; TPB 12.00 +2.13% KL 18,806,500; POW 12.20 0% KL 4,843,200; VIC 215 −1.38%; GAS 76.10 −0.13%. Giá header trắng; màu trên Δ/%.
- **VNINDEX:** 1705.91 +7.56 +0.45% TC 1698.35 — **khớp Realtime atz, không khớp Overview**.
- **UX:** SPA dày; T&S không thấy trên trang mã đã mở; không deep-verify Sổ lệnh.

---

## 4. Đề xuất cho Cursor (tối đa 5, đo được)

1. `[P0]` Sửa nguồn Top KL / bảng giá Overview: dùng bar phiên giao dịch gần nhất (16/10 ngoài phiên 17/10), không lấy TC làm «Giá», loại mã thiếu ngày. **Done khi:** VHM Overview = 61.00 (+3.57%) hoặc cùng hướng Realtime/FireAnt; STB 0.00%; MBB −0.25%; TPB KL phiên ≈ 18,806,500 (±1%); tiêu đề bảng ghi ngày phiên.
2. `[P0]` Thống nhất VNINDEX (và VN30F*) giữa Tổng quan và Realtime cùng nguồn/TC. **Done khi:** ngoài phiên hai màn cùng 1,705.91 +7.56 +0.45% (hoặc ghi rõ nguồn + giờ nếu cố ý khác).
3. `[P1]` Loại chỉ số (VNINDEX…) khỏi Top 20 cổ phiếu; bổ sung mã desk (POW) vào rổ quote board hoặc nhãn «ngoài rổ». **Done khi:** Top 20 không còn dòng chỉ số; lọc `POW` ra 1 dòng hoặc caption rõ «POW chưa trong universe realtime».
4. `[P1]` Format Trần/Sàn như cột Giá; nhãn trạng thái ngoài phiên ≠ `live` (vd. `closed` / `last`); tô bar PnL theo dấu (xanh/đỏ), không dùng màu sàn cho cả hai. **Done khi:** Trần TPB `12,550`; ngoài phiên không hiện `live`; bar TPB xanh / POW đỏ.
5. `[P1]` Contrast zebra/theme: chữ Δ trên nền sọc tối đạt đọc được (hoặc bỏ zebra trên hàng có màu Δ). **Done khi:** hàng HNX/NASDAQ/screener đọc rõ ở 1280×800 không cần zoom.

---

## 5. Việc không nên làm

- Đừng «sửa màu Overview cho khớp board» trước khi sửa bar OHLCV — lệch là dữ liệu/ngày, không phải token màu.
- Đừng đòi hover row icon / Time & Sales stream trên Streamlit dataframe (**BLOCKED** / P2 sản phẩm khác).
- Đừng tăng chu kỳ refresh Top KL; cần đúng phiên, không cần nhanh hơn.
- Không commit ảnh screenshot vào repo.

---

## 6. Resolution (Cursor điền sau khi xử lý)

- **Trạng thái:** `todo`
- **Commit / deploy:**
- **Ghi chú:**
