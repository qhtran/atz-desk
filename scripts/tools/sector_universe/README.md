# Sector universe F3 — lọc mã theo nhóm ngành (nhánh `feat/sector-universe-f3`)

Tool **độc lập app Streamlit**: reverse-engineer list mentor F3 thành tham số lọc tái lập được, chạy **daily / weekly**.

Không sửa `UNIVERSE` / watchlist UI cho đến khi bạn chủ động merge/import.

## Mô hình (Phase 0 + 1 + 3)

| Lớp | Việc |
|-----|------|
| Seed F3 | `config/sector_themes_f3.yaml` — 14 theme mentor |
| Ứng viên | Seed ∪ whitelist ∪ ICB map (trừ mã đã thuộc seed theme khác) |
| Score | `w_gtgd·z(log GTGD20) + w_vol·z(log VOL20) + w_atr·ATR_score` |
| Cắt | `vol20 ≥ min_vol20` (trừ seed/whitelist nếu bật keep) rồi lấy top-K (`k_ratio`) |
| Fit | Grid trên F3 → ghi `fitted` trong `config/sector_universe.yaml` |

Phase 2 (correlation cùng sóng) **chưa** làm trên nhánh này.

## Cài deps

Từ root repo (venv project):

```bash
.venv/bin/python -c "import yaml,pandas,vnstock"
```

**Lưu ý vnstock:** bản `5.0.1` trên máy có thể đã bị nhà phát hành tắt API. Cần nâng:

```bash
.venv/bin/pip install -U 'vnstock>=5.1.0'
```

Trước khi pull đủ bars, tool vẫn chạy được trên cache sẵn có; recall chỉ tính trên mã **đã có** file OHLCV.

## Quy trình lần đầu

```bash
# 0) Đang ở branch đúng chưa?
git branch --show-current   # feat/sector-universe-f3

# 1) Kéo OHLCV cho seed F3 (cache riêng)
.venv/bin/python scripts/tools/sector_universe/pull_bars.py

# (tuỳ chọn) kéo thêm peer ICB — lâu hơn
.venv/bin/python scripts/tools/sector_universe/pull_bars.py --with-peers

# 2) Fit tham số gần F3 và ghi config
.venv/bin/python scripts/tools/sector_universe/fit.py --write-config

# 3) Chạy lọc
.venv/bin/python scripts/tools/sector_universe/run_daily.py
.venv/bin/python scripts/tools/sector_universe/run_weekly.py --refit
```

## Job định kỳ

```bash
# Mỗi ngày sau đóng cửa (có thể kèm --pull)
.venv/bin/python scripts/tools/sector_universe/run_daily.py --pull

# Mỗi tuần: peers + refit + báo cáo
.venv/bin/python scripts/tools/sector_universe/run_weekly.py --pull-peers --refit
```

## Output

```
data/sector_universe/
  ohlcv/                 # cache bars riêng tool
  out/YYYYMMDD/daily/
    by_theme/*.csv
    universe_all.csv
    summary.md
    summary.json
    diff_vs_previous.md  # nếu có run trước
```

## Gap report (S-020)

```bash
.venv/bin/python scripts/tools/sector_universe/fit.py --write-config
.venv/bin/python scripts/tools/sector_universe/report_gap.py
```

Báo cáo: [`docs/specs/F3_SECTOR_UNIVERSE.md`](../../../docs/specs/F3_SECTOR_UNIVERSE.md)  
JSON: `data/sector_universe/out/gap_report.json`

## Test

```bash
.venv/bin/python -m pytest tests/test_sector_universe.py -q
```

## Ranh giới nhánh

- **Có:** config seed/params, scripts tool, tests, cache/out dưới `data/sector_universe/`, spec gap S-020
- **Không (tool lane):** deploy; Phase 2 correlation (future); đổi UI Cảnh báo T-230
