# Color tokens (FireAnt)

Nguồn code: `src/atz/ui/theme_tokens.py`

| Token | Hex | Ý nghĩa |
|-------|-----|---------|
| `UP` | `#00C853` | Tăng / lãi / sparkline tăng |
| `DOWN` | `#FF3D00` | Giảm / lỗ / sparkline giảm |
| `REF` | `#FFC107` | Tham chiếu / đứng giá / nền cột giá mua |
| `CEILING` | `#AB47BC` | Giá trần (tím VN) |
| `FLOOR` | `#29B6F6` | Giá sàn (xanh dương VN) |
| `TEXT_PRIMARY` | `#FFFFFF` | Chữ chính (dark mode) |
| `TEXT_MUTED` | `#9E9E9E` | Chữ phụ (KL, vốn hóa…) |
| `BG_PRIMARY` | `#121418` | Nền app |
| `BG_CARD` | `#1E232A` | Nền thẻ |

**Quy tắc:** số Δ / % / giá theo dấu phiên; sparkline bảng mã = **một màu** theo dấu Δ (không clip TC). Thẻ chỉ số vẫn dùng sparkline clip vàng TC.

**Realtime:** trần `#AB47BC` / sàn `#29B6F6` từ `ceiling_price`/`floor_price` (price_board); thiếu field thì fallback TC × `BAND_*`. Flash nền khi đổi ≥ `flash_min_tick_vnd` (mặc định 50), giữ `flash_hold_cycles` chu kỳ fragment (Giá / +/- / % / Mã).

Đã áp: desk, Tổng quan, Realtime, Top KL, thẻ chỉ số, `config.CHART`.

## Bảng — 3 variants (`ui/table_theme.py` + `render_data_table`)

| Variant | Dùng cho | Ghi chú |
|---------|----------|---------|
| `realtime` | Bảng giá, Top KL | Flash/spark do caller; mật độ dày |
| `analytical` | Tổng quan, desk, watchlist, filter, BCTC… | Pin cột, zebra nhẹ, tô Δ/PnL |
| `compact` | Sidebar, khối ghim, alerts | Thu nhỏ, thay `st.dataframe` thô |

**T-153 contrast:** zebra odd = `BG_CARD` ~25% opacity (`ZEBRA_ODD`); cột signed (Δ/%/PnL) **không** zebra; chữ Δ `font-weight: 700` (`css_up`/`css_down`).

Mọi bảng UI đi qua `render_data_table(variant=...)`. CSS inject một lần (`inject_table_theme`).
