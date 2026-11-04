"""Portfolio valuation & PnL (Milestone 2 Phase 3–4).

Weighted-average cost ledger from ``transactions`` + live ``last`` from
Redis priceboard hash (``load_priceboard_prices``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.desk_portfolio_store import get_portfolio, list_transactions
from backend.portfolio_quotes import load_priceboard_prices


@dataclass
class _LotState:
    qty: float = 0.0
    cost_basis: float = 0.0  # total remaining cost (incl. buy fees allocated)
    realized_pnl: float = 0.0


def _tx_sort_key(tx: dict[str, Any]) -> tuple[str, int]:
    return (str(tx.get("trade_date") or ""), int(tx.get("id") or 0))


def build_cost_ledger(
    transactions: list[dict[str, Any]],
) -> tuple[dict[str, _LotState], float]:
    """Walk trades chronologically → per-symbol WAC state + total realized PnL.

    BUY: qty↑, cost_basis += qty*price + fee
    SELL: realized += (price − avg)*qty − fee; reduce cost_basis by avg*qty
    """
    books: dict[str, _LotState] = {}
    total_realized = 0.0
    for tx in sorted(transactions, key=_tx_sort_key):
        sym = str(tx.get("symbol") or "").strip().upper()
        if not sym:
            continue
        side = str(tx.get("side") or "").strip().upper()
        qty = float(tx.get("quantity") or 0)
        price = float(tx.get("price") or 0)
        fee = float(tx.get("fee") or 0)
        if qty <= 0 or price <= 0:
            continue
        lot = books.setdefault(sym, _LotState())
        if side == "BUY":
            lot.qty += qty
            lot.cost_basis += qty * price + fee
        elif side == "SELL":
            if lot.qty <= 1e-12:
                continue
            sell_qty = min(qty, lot.qty)
            avg = lot.cost_basis / lot.qty if lot.qty else 0.0
            realized = (price - avg) * sell_qty - fee
            # If oversold in bad data, fee still applied once on requested sell.
            if sell_qty < qty:
                realized = (price - avg) * sell_qty - fee
            lot.realized_pnl += realized
            total_realized += realized
            lot.cost_basis -= avg * sell_qty
            lot.qty -= sell_qty
            if lot.qty <= 1e-12:
                lot.qty = 0.0
                lot.cost_basis = 0.0
        # else ignore unknown side
    return books, total_realized


def open_holdings_from_ledger(
    books: dict[str, _LotState],
) -> list[dict[str, Any]]:
    """Open positions (qty > 0) with avg_cost / cost_basis / realized_pnl."""
    out: list[dict[str, Any]] = []
    for sym in sorted(books.keys()):
        lot = books[sym]
        if lot.qty <= 1e-9:
            # closed symbol still contributes realized via summary total
            continue
        avg = lot.cost_basis / lot.qty if lot.qty else 0.0
        out.append(
            {
                "symbol": sym,
                "qty": round(lot.qty, 6),
                "avg_cost": round(avg, 6),
                "cost_basis": round(lot.cost_basis, 2),
                "realized_pnl": round(lot.realized_pnl, 2),
            }
        )
    return out


def closed_realized_from_ledger(books: dict[str, _LotState]) -> float:
    """Sum realized across all symbols (open + closed)."""
    return round(sum(lot.realized_pnl for lot in books.values()), 2)


def value_holdings(
    holdings: list[dict[str, Any]],
    prices: dict[str, float],
    *,
    total_value_for_weight: float | None = None,
) -> tuple[list[dict[str, Any]], float, float]:
    """Attach last_price, market_value, unrealized PnL, weight_pct.

    Returns (enriched_rows, stock_market_value, unrealized_pnl_total).
    """
    enriched: list[dict[str, Any]] = []
    stock_mv = 0.0
    unreal = 0.0
    for h in holdings:
        sym = h["symbol"]
        qty = float(h["qty"])
        avg = float(h["avg_cost"])
        cost = float(h.get("cost_basis") if h.get("cost_basis") is not None else avg * qty)
        last = prices.get(sym)
        last_f = float(last) if last is not None and float(last) > 0 else None
        mv = (last_f * qty) if last_f is not None else None
        u_pnl = ((last_f - avg) * qty) if last_f is not None else None
        u_pct = (((last_f - avg) / avg) * 100.0) if last_f is not None and avg > 0 else None
        if mv is not None:
            stock_mv += mv
        if u_pnl is not None:
            unreal += u_pnl
        enriched.append(
            {
                **h,
                "last_price": last_f,
                "market_value": round(mv, 2) if mv is not None else None,
                "unrealized_pnl": round(u_pnl, 2) if u_pnl is not None else None,
                "unrealized_pnl_pct": round(u_pct, 4) if u_pct is not None else None,
                "weight_pct": None,  # filled below
            }
        )

    denom = float(total_value_for_weight) if total_value_for_weight is not None else stock_mv
    for row in enriched:
        mv = row.get("market_value")
        if mv is not None and denom and denom > 0:
            row["weight_pct"] = round(float(mv) / denom * 100.0, 4)
        else:
            row["weight_pct"] = 0.0 if row.get("qty") else None
    return enriched, round(stock_mv, 2), round(unreal, 2)


def portfolio_summary(
    user_id: str,
    portfolio_id: int,
    *,
    prices: dict[str, float] | None = None,
    db_path: Path | None = None,
    redis_url: str | None = None,
) -> dict[str, Any] | None:
    """Full portfolio summary or ``None`` if missing / not owned."""
    folio = get_portfolio(user_id, portfolio_id, db_path=db_path)
    if folio is None:
        return None
    txs = list_transactions(user_id, portfolio_id, db_path=db_path) or []
    books, _ = build_cost_ledger(txs)
    holdings = open_holdings_from_ledger(books)
    realized = closed_realized_from_ledger(books)

    syms = [h["symbol"] for h in holdings]
    if prices is None:
        kwargs: dict[str, Any] = {}
        if redis_url:
            kwargs["redis_url"] = redis_url
        prices = load_priceboard_prices(syms, **kwargs) if syms else {}

    cash = float(folio.get("cash_balance") or 0)
    # Pass 1: market values; pass 2 weights vs cash + stock.
    enriched, stock_mv, unreal = value_holdings(holdings, prices)
    total_value = round(cash + stock_mv, 2)
    if total_value > 0:
        for row in enriched:
            mv = row.get("market_value")
            row["weight_pct"] = (
                round(float(mv) / total_value * 100.0, 4) if mv is not None else 0.0
            )

    return {
        "portfolio_id": int(folio["id"]),
        "name": folio["name"],
        "cash_balance": round(cash, 2),
        "stock_market_value": stock_mv,
        "total_value": total_value,
        "unrealized_pnl": unreal,
        "realized_pnl": realized,
        "holdings": enriched,
    }
