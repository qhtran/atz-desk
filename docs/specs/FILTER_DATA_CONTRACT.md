# Filter data contract (research / iBoard daily-signals)

**Mục đích:** Mỗi filter khai báo dữ liệu tối thiểu — tránh lưu tick thừa, biết khi nào mở rộng `data/market.db`.

## Đã ship trên iBoard (`ALLOWED_FILTERS`)

| Filter | Timeframe | min_bars | Columns | Nguồn local |
|--------|-----------|----------|---------|-------------|
| rsi | daily | ~30 | O,H,L,C,V | `data/ohlcv/{SYM}.csv` |
| macd | daily | ~35 | O,H,L,C,V | ohlcv CSV |
| ma | daily | param | O,H,L,C | ohlcv CSV |
| candle | daily | ~5 | O,H,L,C | ohlcv CSV |
| volume | daily | ~20 | V (+ avg) | ohlcv CSV |
| foreign | daily | ~5 | flow KN | `data/flow` |
| advisor | daily | ~60 | O,H,L,C,V | ohlcv + engine YAML |
| bollinger | daily | 20 | C | ohlcv CSV |
| adx | daily | ~30 | H,L,C | ohlcv CSV |
| atr | daily | ~35 | H,L,C,O | ohlcv CSV |
| rs_index | daily | 60 | C + VNINDEX | ohlcv CSV |
| breakout_52w | daily | 252 | H,C | ohlcv CSV |
| stochastic | daily | ~20 | H,L,C | ohlcv CSV |

## Hàng đợi P1 (daily OHLCV — F-01…F-10)

| ID | Filter | min_bars | Columns | Trạng thái |
|----|--------|----------|---------|------------|
| F-01 | Bollinger | 20 | C (+ H,L) | **Shipped** iBoard |
| F-02 | ADX | 28 | H,L,C | **Shipped** iBoard |
| F-03 | ATR | 15 | H,L,C | **Shipped** iBoard |
| F-04 | RS vs VNINDEX | 60 | C + index C | **Shipped** iBoard |
| F-05 | Breakout 52w | 252 | H,C | **Shipped** iBoard |
| F-06 | MA cross | 50 | C | **Shipped** (filter `ma`) |
| F-07 | Stochastic | 14 | H,L,C | **Shipped** iBoard |
| F-08 | Foreign streak | N | foreign_net series |
| F-09 | Liquidity | 20 | V, GT |
| F-10 | Market regime | 200 | VNINDEX C |

**Archive đủ P1:** `equity_eod` + `foreign_eod` trong `data/market.db` (job `market_ingest` / mở rộng `ohlcv_seed`).

## P2 / P3 (backlog)

Xem plan index-bar — F-11…F-19 (fundamental, sector, intraday VWAP, …).

## Storage milestone (~300 user)

| Khối | Giai đoạn hiện tại | Scale |
|------|-------------------|--------|
| `market.db` (EOD, index 1m) | SQLite WAL, 1 writer job | Giữ; scan nặng → Parquet/DuckDB export |
| User portfolio / trading | SQLite dev | **Postgres** khi ~300 user ghi đồng thời |
| Kết quả quét (gold) | Cache in-memory / optional table | Precompute theo `(trading_date, filter)` |

Không nhân bản EOD theo user — một bản shared trên VPS.
