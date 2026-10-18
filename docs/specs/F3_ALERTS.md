# F3 Cảnh báo — catalog rule & contract (S-010)

**Status:** **Master ack Pass** (2026-10-18) — sẵn sàng T-230 khi human START  
**Owner draft:** ag3 / sp1  
**Consumers:** ag2 T-230 (UI + engine)  
**Nguồn mentor:** CHỈNH SỬA LẦN F3 — cột «Cảnh báo» trong Danh mục theo nhóm ngành  
**Ngày:** 2026-10-18  

---

## 1. Mục tiêu

Định nghĩa contract để cột **Cảnh báo** trên tab Danh mục (sau khi user chọn một ngành F3) hiển thị câu chữ có cấu trúc theo mã: xu hướng ngày + thủng hỗ trợ / vượt kháng cự trên các level mentor liệt kê.

Đây là lớp **decision-support** (UI; optional Telegram cùng format).  
**Không** phải pipeline đặt lệnh; **không** sinh Intent / Order / gọi broker.

---

## 2. Quyết định ag1 đã khóa (bắt buộc)

1. **Chỉ UI** (+ optional Telegram cùng format câu chữ) — **không** Intent / order path / paper-order / %NAV sizing.  
2. **Priority:** chờ mentor. UI tạm **liệt kê tất cả** câu khớp, ghép bằng ` · `. Provisional rank (mục 7) chỉ note nội bộ — **cấm** dùng auto-size.  
3. **Cooldown / dedup:** riêng UI/alert — **không** gắn cooldown order-path (Risk gate bước 2).  
4. **Tách feed:** rule F3 khung **ngày** ≠ «Chat 1 phiên» / intraday spark.

---

## 3. Inputs kỹ thuật

| Input | Định nghĩa | Ghi chú |
|-------|------------|---------|
| `symbol` | Mã trong danh mục ngành F3 | Seed: `config/sector_themes_f3.yaml` (khi UI nạp) |
| `bars_D` | OHLCV khung **ngày** đủ tính MA/BB/Ichimoku/đáy-đỉnh | Tối thiểu đủ MA200 + BB(20) + mây |
| `close` | Giá đóng / last dùng để so level (ngày) | T-230 chọn: last RT vs close D — **open Q** mentor nếu lệch |
| `prev_close` / `prev_bar` | Nến trước để phát hiện **cross** (thủng / vượt) | Cần để không spam khi giá đã nằm dưới level nhiều phiên |
| Indicators | MA20/50/100/200; BB upper/mid/lower (std mentor/app); Ichimoku cloud top/bottom; swing high/low | Tái dùng `analysis/technical` + support scan khi T-230 |

### OUT — không dùng làm input F3 Cảnh báo

- Intraday 1 phiên («Chat» cột riêng).  
- Khối lượng / NAV / margin / tín hiệu filter F2 mua (BB squeeze…) — trừ khi mentor bổ sung sau.

---

## 4. Event rules

### 4.1 Xu hướng ngày

| State | Rule gợi ý (T-230 được tinh chỉnh, ghi rõ trong PR) |
|-------|-----------------------------------------------------|
| `tăng` | Cấu trúc giá ngày nghiêng lên (vd. close > MA20 và MA20 dốc lên; hoặc close > close[N]) |
| `giảm` | Ngược lại |
| `sideway` | Không đủ điều kiện tăng/giảm rõ |

Luôn phát **một** dòng xu hướng (kể cả khi không có sự kiện thủng/vượt).

### 4.2 Hỗ trợ — chỉ khi giá **giảm thủng** level

Điều kiện chung (hướng):

- Cross xuống: `prev` ở trên / trên-bằng level và `close` (hoặc low) **cắt xuống dưới** level theo tolerance T-230 (vd. 0 hoặc `SUPPORT_BAND`).

Levels:

| `level_kind` | Level value |
|--------------|-------------|
| `MA20` | MA(20) |
| `MA50` | MA(50) |
| `MA100` | MA(100) |
| `MA200` | MA(200) |
| `BB_upper` | Bollinger biên trên |
| `BB_mid` | Bollinger band giữa |
| `BB_lower` | Bollinger biên dưới (ra ngoài band) |
| `CLOUD_upper` | Biên trên mây Ichimoku |
| `CLOUD_lower` | Biên dưới mây |
| `SWING_LOW` | Vùng đáy gần nhất (giá cụ thể) |
| `SWING_HIGH` | Vùng đỉnh dùng như hỗ trợ khi thủng (mentor: «hỗ trợ đáy/đỉnh») |

### 4.3 Kháng cự — khi giá **tăng từ dưới** chạm/vượt level

Cùng tập `level_kind`, chiều ngược:

- Cross lên: `prev` dưới level và `close` (hoặc high) cắt lên trên level.

### 4.4 Multi-hit

Một mã có thể khớp nhiều level cùng phiên → **liệt kê tất cả** (ag1).  
Không rank để cắt bớt trên UI cho đến khi mentor chốt.

---

## 5. Text templates (contract câu chữ)

### 5.1 Xu hướng

```text
xu hướng ngày: tăng
xu hướng ngày: giảm
xu hướng ngày: sideway
```

### 5.2 Hỗ trợ (giảm thủng)

Mẫu gốc mentor:

```text
giảm thủng hỗ trợ <loại> <giá>
```

Biến thể đã reverse từ mentor (giữ ngữ nghĩa; T-230 normalize số thập phân 1–2 chữ số theo giá VN):

| level_kind | Template |
|------------|----------|
| MA* | `giảm thủng hỗ trợ MA20 12.2` (tương tự MA50/100/200) |
| BB_upper | `giảm thủng biên trên band 12.2` |
| BB_mid | `giảm thủng band giữa 12.2` |
| BB_lower | `giá đi ra ngoài band dưới 12.2` |
| CLOUD_upper | `thủng biên trên mây (giá đi vào trong mây) 12.2` |
| CLOUD_lower | `giá đi xuống dưới mây 12.2` |
| SWING_LOW | `giảm thủng vùng hỗ trợ đáy 12.2` |
| SWING_HIGH | `giảm thủng vùng hỗ trợ đỉnh 12.2` |

### 5.3 Kháng cự (tăng vượt)

```text
vượt kháng cự <loại> <giá>
```

Ví dụ: `vượt kháng cự MA50 15.3` · `vượt kháng cự biên trên band 16.0` · `vượt kháng cự vùng đỉnh 16.5`.

(T-230 giữ parallel naming với bảng hỗ trợ; nếu mentor đưa wording cứng hơn thì cập nhật spec patch.)

### 5.4 Ghép cột UI

```text
<xu hướng> · <câu 1> · <câu 2> · …
```

Ví dụ:

```text
xu hướng ngày: giảm · giảm thủng hỗ trợ MA20 12.2 · giảm thủng band giữa 12.1
```

Nếu chỉ có xu hướng: chỉ một cụm xu hướng.

---

## 6. UI column contract (Danh mục ngành F3)

### 6.1 Điều hướng (ngữ cảnh — không thuộc engine alert)

1. User mở **Danh mục** → thấy 14 nhóm ngành F3.  
2. Chọn một ngành → bảng mã ngành đó.

### 6.2 Cột bảng khi đã chọn ngành

| Cột | Nội dung | Feed |
|-----|----------|------|
| Danh sách | Mã F3 của ngành | Catalog seed |
| Giá | Giá hiện tại RT (HSX/HNX/UPCoM boards) | Quote RT — **ngoài** S-010 |
| Chat | Spark **1 phiên** (mở cửa → now) | Intraday — **OUT** của F3 alert |
| **Cảnh báo** | String mục 5.4 | Engine này (khung ngày) |
| Bài viết/cộng đồng | News + chat theo mã + moderation | Module riêng — **OUT** S-010 |

### 6.3 Hành vi cột Cảnh báo

- Empty / `—` nếu thiếu bars đủ indicator.  
- Dedup UI: **tối đa 1 câu / (mã, level_kind, direction) / ngày giao dịch**, hoặc đến khi state cross đổi (hết thủng → clear).  
- Không mở order ticket từ click cảnh báo (NON-goal).

---

## 7. Dedup / cooldown (UI-only)

| Tham số đề xuất | Giá trị |
|-----------------|---------|
| Key | `(symbol, level_kind, direction, session_date)` |
| Emit | Lần đầu cross trong phiên ngày |
| Re-emit | Chỉ khi flip state (vd. lại vượt lên rồi thủng lại) |
| Không dùng | Order-path cooldown / max lệnh/ngày |

---

## 8. Map kiến trúc (vs pipeline lệnh 8 bước)

```text
bars_D + indicators
        → F3 Alert engine
        → UI cột «Cảnh báo» (+ optional Telegram cùng format)
        ✗ không → Risk / Position / Order / Broker / Fill
```

| Pipeline bước | F3 Cảnh báo |
|---------------|-------------|
| 1 Signal→Intent | **Không** nuôi Intent (ag1 khóa). Chỉ display. |
| 2–6 Risk…Fill | **Cấm** bypass / gắn |
| 7 Post-trade & alerts | Có thể **tái dùng format câu chữ** cho Telegram — vẫn không phải post-trade bắt buộc |
| 8 Kill-switch | Không liên quan trực tiếp |

NON-goal sản phẩm hiện tại: không đặt lệnh tự động (PROGRESS §1).

---

## 9. Provisional rank (nội bộ only — không UI-cut, không auto-size)

Chỉ để review/debug nội bộ T-230; **không** filter cột, **không** sizing:

1. SWING_LOW / SWING_HIGH  
2. MA200 → MA100 → MA50 → MA20  
3. CLOUD_*  
4. BB_lower / BB_upper → BB_mid  
5. Xu hướng (luôn kèm, không rank)

---

## 10. NON-goals (S-010 / T-230 scope guard)

- Sửa production ngoài task T-230 khi được START.  
- Sinh Intent / paper-order / broker adapter.  
- Auto-size theo độ “nặng” cảnh báo.  
- Trộn logic «Chat 1 phiên» vào engine cảnh báo ngày.  
- Rank mentor chưa chốt làm hard filter UI.

---

## 11. Open questions (chờ mentor / ag1)

1. So level bằng **last RT** hay **close ngày** khi trong phiên?  
2. Tolerance thủng (tick / % / `SUPPORT_BAND`)?  
3. Wording kháng cự mentor có cứng hơn `vượt kháng cự …` không?  
4. Có cần icon/màu theo tăng/giảm trên cột không (F1 FireAnt)?  
5. Telegram optional: bật per-user hay global kill-switch?

---

## 12. Handoff tip cho T-230 (ag2) — ≤15 dòng

1. Đọc spec này + ag1 START T-230; **không** start trước Master ack S-010.  
2. Engine thuần: `bars_D` → list `AlertPhrase`; ghép ` · `; không đụng order_helper.  
3. Tái dùng indicator sẵn (`analysis/technical`, support/swing nếu có); đừng nhân bản BB/MA.  
4. UI: cột trong bảng ngành F3 (Watchlist) — string + tooltip raw list nếu dài.  
5. Dedup key mục 7; persist nhẹ (session/SQLite) tuỳ PR — không dùng alert_dispatcher order cooldown.  
6. Unit test: cross xuống MA20 → đúng template; không cross → không câu; multi-level → đủ câu.  
7. **Cấm:** Intent, %NAV, broker. Chat intraday / Giá RT / community = task khác.  
8. Open Q mục 11: default hợp lý + ghi chú PR nếu mentor chưa trả lời.

---

## 13. Acceptance trace (S-010)

| Hạng mục | Có trong spec |
|----------|----------------|
| Inputs | §3 |
| Event rules | §4 |
| Text templates | §5 |
| UI column contract | §6 |
| NON-goals | §10 + §2 |
| Open questions mentor | §11 |
| Handoff tip T-230 ≤15 dòng | §12 |
| ag1 locks | §2 |

**S-010 Done** khi file này merged/ack và Last Support state = Done trên `PROGRESS.md`.  
**Không** tự chuyển T-230 → Doing.
