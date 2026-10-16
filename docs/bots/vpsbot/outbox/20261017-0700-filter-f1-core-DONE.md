# Outbox VPSbot — filter F1 core (nến / RSI / MACD)

- **Status:** DONE
- **Brief:** `docs/bots/vpsbot/inbox/20261017-0700-filter-f1-core.md`
- **HEAD (code):** `dee39bf` feat(filters): tighten candle/RSI/MACD to the F1 criteria
- **Deploy:** yes — `vnstocks` + `filter-runner` (cùng image, logic chạy nền đổi)
- **merge_main:** yes — commit thẳng trên `main`, push thường (không force)

## Summary

Siết 3 filter F1 mục 7 hàng 1–3 cho khớp checklist. Mỗi filter có thêm param `mode`
(`f1` mặc định, `co_ban` = logic phiên-cuối cũ). Thiếu cột / thiếu phiên → `SignalResult`
`cho` với reason rõ ("không đủ dữ liệu: …"), không raise. Catalog `ui/filter_criteria.py`
map từng hàng sang tên filter trong registry (`F1_FILTERS`), có test kiểm tra map.
Không đụng Bollinger / Ichimoku / phần II, nginx, secret.

## Notes — map tiêu chí → hàm code

| F1 | Tiêu chí | Filter (registry) | Hàm analysis | Điều kiện `mua` (mode f1) |
|----|----------|-------------------|--------------|---------------------------|
| 7.1 | Nến Nhật — đảo chiều tại hỗ trợ | `candle` (`filters/candle.py::_f1`) | `analysis/candles.py::reversal_at_support` (dùng `candle_pattern` + `analysis/support.py::support_scan`) | Phiên cuối là Engulfing tăng hoặc Hammer **và** low thấp nhất 2 phiên cuối ≤ `zone_top` (đáy 6 tháng × (1 + `SUPPORT_BAND`)). Nến giảm → `giu` (F1 chỉ chiều mua). details: `pattern`, `at_support`, `support`, `zone_top`, `support_tests` |
| 7.2 | RSI — 2–3 đáy vùng ~30, vượt đáy trung tâm | `rsi` (`filters/rsi.py::_f1`) | `analysis/technical.py::rsi_bottoms` (trên `rsi()` Wilder) | ≥ `min_bottoms` (2) đáy RSI (cực tiểu ±3 phiên) ≤ `oversold + bottom_band` (30 + 5) trong `lookback` (60) phiên, **và** RSI phiên cuối vừa vượt "đáy trung tâm" RSI = đỉnh RSI cao nhất giữa đáy đầu và đáy cuối (cùng định nghĩa neckline của `support_scan`) |
| 7.3 | MACD — cắt lên Signal + histogram cải thiện ≥ 2 phiên | `macd` (`filters/macd.py::_f1`) | `analysis/technical.py::macd_improving` (trên `macd()`) | MACD cắt lên Signal trong `cross_window` (3) phiên gần nhất **và** histogram tăng liên tiếp `improve_bars` (2) phiên |

- Nến **mạnh / TB / yếu**: code chưa có enum nào → chưa gắn (brief: "nếu code đã có enum"). Chỉ trả `support_tests` (số lần chạm hỗ trợ) trong details để tham khảo; cần mentor định nghĩa.
- "Vượt đáy trung tâm" ở hàng RSI hiểu là RSI vượt đỉnh RSI giữa các đáy (tương tự neckline giá). Nếu mentor muốn là **giá** vượt neckline của `support_scan`, chỉ cần đổi điều kiện trong `rsi._f1`.
- Đáy RSI cuối chỉ được xác nhận sau 3 phiên; nếu RSI vượt neckline ngay trong 3 phiên đó thì lần cắt đó không bắt được.
- **Đổi hành vi production:** user không có config (`default_filters` rsi/macd trong `config/filter_runner.yaml`) và config đã lưu không có `mode` giờ chạy F1 → ít tín hiệu hơn. Muốn logic cũ: chọn "Chế độ = co_ban" trong Bộ lọc tín hiệu.
- `support_scan` giờ tự suy `_day` từ `time` khi thiếu (bars của runner/test); hành vi cũ khi có `_day` giữ nguyên.

## Files

- `src/atz/filters/candle.py`, `src/atz/filters/rsi.py`, `src/atz/filters/macd.py`
- `src/atz/analysis/candles.py`, `src/atz/analysis/technical.py`, `src/atz/analysis/support.py`
- `src/atz/ui/filter_criteria.py`
- `tests/test_filter_f1.py` (mới, 17 test), `tests/test_filter_criteria.py`, `tests/test_candle.py`, `tests/test_rsi.py`, `tests/test_macd.py`, `tests/test_filter_runner.py` (test plumbing runner pin `mode: co_ban`)
- `docs/F1_CHECKLIST_UI.md` (tick mục 7 siết logic)

## Tests — PASS

```
docker run --rm --network vnstocks_realtime -v /opt/vnstocks:/src:ro --tmpfs /src/data -w /src \
  -e PYTHONPATH=/src/src vnstocks-vnstocks python -m pytest -q tests
→ 191 passed, 1 skipped, 3 failed
```

Module liên quan: `test_filter_f1 test_filter_criteria test_candle test_rsi test_macd test_registry test_composite test_engine` → **39 passed**.

3 fail còn lại **có sẵn trên HEAD trước brief** (đã chạy lại trên worktree `6637b14` để so), không liên quan:
- `test_filter_runner::test_integration_real_ingestion_stream` (cần stream/DB thật)
- `test_ingestion::test_t1_real_kbs_batch_normalized_and_cached` (vnstock gọi mạng: "could not obtain its current client policy")
- `test_ui_realtime::test_t1_refresh_interval_trading_hours` (5.0 != 3, cấu hình refresh)

## Commands (rút gọn)

```
cd /opt/vnstocks && git pull --ff-only
# sửa code + test, chạy pytest như trên
git commit -m "feat(filters): tighten candle/RSI/MACD to the F1 criteria" && git push origin main
DOCKER_BUILDKIT=1 docker compose build vnstocks
docker compose up -d --no-deps vnstocks filter-runner
docker ps   # vnstocks Up, atz-filter-runner Up (healthy)
docker exec vnstocks python -c "...load_registry()..."  # candle/rsi/macd mode default = f1
```

## Rủi ro còn lại

- Ngưỡng F1 (vùng 30+5, lookback 60, cross_window 3, improve 2) là mặc định hợp lý, chưa được mentor xác nhận — chỉnh qua param, không cần deploy.
- Mạnh/TB/yếu nến + Bollinger/Ichimoku/phần II vẫn chờ mentor.
