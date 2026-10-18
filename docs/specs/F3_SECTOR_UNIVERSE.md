# F3 Sector Universe — reverse-fit & gap report (S-020)

**Status:** Spec Ready (chờ Master ack)  
**Owner:** ag3 / sp1  
**Generated:** `2026-10-18T04:46:59+00:00`  
**Branch:** `feat/sector-universe-f3`  
**Tool:** `scripts/tools/sector_universe/`  

## 1. Mục tiêu

Document độ gần model lọc thematic so với seed mentor F3: recall / precision / gap.
Không đổi UI T-230; không deploy; Phase 2 correlation = future.

## 2. Fitted params (đang dùng)

Nguồn: khối `fitted` trong `config/sector_universe.yaml` (sau `fit.py --write-config`).

| Param | Value |
|-------|-------|
| `w_log_gtgd` | `0.45` |
| `w_log_vol` | `0.25` |
| `w_atr` | `0.05` |
| `min_vol20` | `300000.0` |
| `k_ratio` | `0.9` |
| `k_min` / `k_max` | `5` / `22` |
| `keep_seed_if_listed` | `True` |
| `keep_whitelist` | `True` |

Score: `w_gtgd·z(log GTGD20) + w_vol·z(log VOL20) + w_atr·ATR_score` rồi top-K theo `k_ratio`.

## 3. Coverage dữ liệu (ràng buộc chính)

| Metric | Value |
|--------|-------|
| Seed mentor (unique) | **181** |
| Seed có OHLCV đủ `min_bars` | **33** |
| Seed thiếu bars | **148** |
| Bars dir | `/Users/tqhoai/PycharmProjects/vnstocks/data/sector_universe/ohlcv` |

**Lưu ý:** `vnstock==5.0.1` trên máy dev có thể bị tắt API → `pull_bars.py` fail.
Recall bên dưới chỉ tính trên seed **đã có bars** (không phạt thiếu cache).
Muốn số liệu đầy đủ: nâng `vnstock>=5.1.0` rồi `pull_bars.py` (+ optional `--with-peers`) + `fit.py --write-config`.

### Seed thiếu bars (sample)

AAA, ACV, ANV, APH, ASM, BAF, BCF, BCM, BMP, BSI, BSR, BTP, BVB, BVS, C4G, CDN, CEO, CHP, CII, CMG, CNG, CRV, CSM, CSV, CTD, CTR, CTS, D2D, DBC, DCM, DDV, DGC, DGW, DPG, DPM, DPR, DRC, DTD, DVP, ELC …

## 4. Bảng tóm tắt theo theme

Macro (theme có bars): **recall=100.0%** · **precision=98.0%** · themes scored=10/14

| Theme | Seed | Có bars | Selected | Recall | Precision | Hit | Miss (seed+bars) | FP (sample) |
|-------|-----:|--------:|---------:|-------:|----------:|----:|------------------|-------------|
| chung_khoan | 17 | 3 | 3 | 100% | 100% | 3 | — | — |
| ngan_hang | 20 | 12 | 12 | 100% | 100% | 12 | — | — |
| bds_nha_o | 20 | 4 | 5 | 100% | 80% | 4 | — | PDR |
| bds_cong_nghiep | 13 | 0 | 1 | 0% | 0% | 0 | — | PDR |
| thep | 5 | 1 | 1 | 100% | 100% | 1 | — | — |
| xay_lap | 12 | 0 | 0 | 0% | 0% | 0 | — | — |
| cang_van_tai | 13 | 1 | 1 | 100% | 100% | 1 | — | — |
| ban_le | 10 | 5 | 5 | 100% | 100% | 5 | — | — |
| dau_khi | 13 | 3 | 3 | 100% | 100% | 3 | — | — |
| hoa_chat | 17 | 0 | 0 | 0% | 0% | 0 | — | — |
| hang_khong | 6 | 1 | 1 | 100% | 100% | 1 | — | — |
| nang_luong | 17 | 2 | 2 | 100% | 100% | 2 | — | — |
| nong_nghiep | 12 | 0 | 0 | 0% | 0% | 0 | — | — |
| cong_nghe | 6 | 1 | 1 | 100% | 100% | 1 | — | — |

## 5. Gap analysis

### 5.1 Mentor miss (có bars nhưng model không giữ)

- Count: **0**
- List: —

Với `keep_seed_if_listed=true`, miss chỉ xảy ra khi seed **không có bars** đủ hoặc bị loại khỏi top-K sau khi không pass vol và không keep — kiểm tra lại nếu count > 0 khi đủ data.

### 5.2 False positive (model chọn ngoài seed)

- Count (theme-tagged): **2** (liệt kê mẫu trong bảng §4).
- Thường là peer ICB thanh khoản cao lọt top-K — đúng hành vi “mở rộng thematic”, không nhất thiết lỗi.

### 5.3 Theme 0 bars

bds_cong_nghiep, xay_lap, hoa_chat, nong_nghiep

## 6. Kết luận S-020

1. Pipeline reverse-fit **chạy được** (fit/score/daily) trên cache hiện có.
2. Trên subset có bars: recall cao nhờ `keep_seed_if_listed` — đây là gần mentor theo thiết kế Phase 1.
3. **Blocker số liệu đầy đủ:** thiếu OHLCV ~148 mã seed → cần pull lại sau khi nâng vnstock.
4. Future (không làm S-020): Phase 2 correlation cùng sóng; import UI catalog đã có qua T-230 seed loader.

## 7. Lệnh tái tạo report

```bash
.venv/bin/python scripts/tools/sector_universe/fit.py --write-config
.venv/bin/python scripts/tools/sector_universe/report_gap.py
.venv/bin/python scripts/tools/sector_universe/run_daily.py
```

