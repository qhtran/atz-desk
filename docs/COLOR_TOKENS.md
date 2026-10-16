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

Đã áp: desk, Tổng quan, Realtime, Top KL, thẻ chỉ số, `config.CHART`.
