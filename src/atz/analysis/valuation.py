"""P/E và P/B so với trung vị cùng ngành ICB trong danh sách quét."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from config import UNIVERSE, WORKERS
from datasource.fundamentals import industry_table, multiples, read_valuation, store_valuation


def valuation_board(symbol: str) -> tuple[pd.DataFrame, str, float | None, float | None]:
    """P/E, P/B của mã và trung vị các mã cùng ngành ICB cấp 3 trong danh sách quét."""
    industries = industry_table()
    names = industries.set_index("symbol")["icb_name"]
    industry = names.get(symbol)
    if industry is None or (isinstance(industry, float) and pd.isna(industry)):
        raise ValueError("không thấy nhóm ngành")
    peers = [item for item in UNIVERSE if names.get(item) == industry]
    if symbol not in peers:
        peers = [symbol, *peers]
    stored = read_valuation().set_index("Mã")
    missing = [item for item in peers if item not in stored.index]
    fetched: list[dict[str, object]] = []
    if missing:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            fetched.extend(pool.map(multiples, missing))
        store_valuation(fetched)
        stored = read_valuation().set_index("Mã")
    records: list[dict[str, object]] = []
    for item in peers:
        if item in stored.index:
            row = stored.loc[item]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            pe = pd.to_numeric(row["P/E"], errors="coerce")
            pb = pd.to_numeric(row["P/B"], errors="coerce")
        else:
            pe = pd.NA
            pb = pd.NA
        records.append(
            {
                "Mã": item,
                "Vai trò": "Mã đang chọn" if item == symbol else "Đối thủ",
                "P/E": None if pd.isna(pe) else float(pe),
                "P/B": None if pd.isna(pb) else float(pb),
            }
        )
    board = pd.DataFrame(records)
    rivals = board.loc[board["Mã"] != symbol, "P/E"]
    rival_pb = board.loc[board["Mã"] != symbol, "P/B"]
    pe_median = float(rivals.median()) if rivals.notna().any() else None
    pb_median = float(rival_pb.median()) if rival_pb.notna().any() else None
    return board, str(industry), pe_median, pb_median
