"""Chỉ publish khi quote thay đổi (giá, khối lượng, cao/thấp)."""
from __future__ import annotations

from ingestion.normalizer import Quote


def fingerprint(quote: Quote) -> tuple:
    return (quote.price, quote.volume, quote.high, quote.low, quote.ref_price)


class ChangeDetector:
    def __init__(self):
        self.last: dict[str, tuple] = {}

    def changed(self, quote: Quote) -> bool:
        key = fingerprint(quote)
        if self.last.get(quote.symbol) == key:
            return False
        self.last[quote.symbol] = key
        return True
