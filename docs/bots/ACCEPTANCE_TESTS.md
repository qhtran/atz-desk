# Bộ test chấp nhận (AuditorBot + tham chiếu VPSbot)

Môi trường: **https://atz.vn** (sau auth nếu cần) · đối chiếu **https://fireant.vn**.  
Ghi Pass/Fail/BLOCKED từng case trong báo cáo inbox.

## A. Màu & giới hạn giá (P0)

| ID | Case | Pass khi |
|----|------|----------|
| A1 | Mã tăng | Giá/Δ/% xanh ≈ `#00C853` (không vàng nhầm) |
| A2 | Mã giảm | Đỏ ≈ `#FF3D00` |
| A3 | Đứng tham chiếu | Vàng/amber ≈ `#FFC107` hoặc tương đương TC |
| A4 | Trần | Tím ≈ `#AB47BC` khi giá = trần (hoặc ghi không quan sát được trong phiên) |
| A5 | Sàn | Xanh dương ≈ `#29B6F6` khi giá = sàn |

## B. Realtime board (P0–P1)

| ID | Case | Pass khi |
|----|------|----------|
| B1 | Search mã | Gõ 1–3 ký tự lọc được bảng |
| B2 | Cập nhật | Trong 1–2 phút thấy giá đổi hoặc ghi «phiên nghỉ / không đổi» |
| B3 | Flash | Nền nháy khi đổi giá — Fail → P2/BLOCKED Streamlit nếu không có |

## C. Sidebar vị thế (P1)

| ID | Case | Pass khi |
|----|------|----------|
| C1 | Khối «Tổng quan vị thế» | Có vốn / NAV / danh sách mã |
| C2 | Giá hiện tại | Khác rõ giá đóng cửa cũ nếu thị trường sống; hoặc Notes «Redis miss / phiên nghỉ» |
| C3 | Cảnh báo | Có text gần hỗ trợ/kháng / ±% |

## D. Tổng quan & tin (P1)

| ID | Case | Pass khi |
|----|------|----------|
| D1 | Top KL | Expander/bảng ~20 mã, không crash |
| D2 | RSS | Không lộ thẻ HTML thô (`<div>`, `<script>`…) |

## E. Regress sau deploy sidebar (Auditor task 0700)

| ID | Case | Pass khi |
|----|------|----------|
| E1 | C2 sau deploy | Giá sidebar khớp hướng với board realtime cùng mã (± lệch làm tròn OK) |
| E2 | Không regression A1–A5 | Màu board không vỡ |

## Ghi Fail

Tag P0/P1/P2/BLOCKED + loại (thiếu SP / giới hạn Streamlit) + 1 bước tái hiện.
