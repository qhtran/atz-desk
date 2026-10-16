"""Hợp đồng Signal (tài liệu mục 3) - đúng 9 trường."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

DIRECTIONS = {"mua": "BUY", "ban": "SELL"}


@dataclass
class Signal:
    signal_id: str
    user_id: str
    symbol: str
    timestamp: str        # ISO +07:00
    filter_name: str
    direction: str        # BUY | SELL
    price: float
    reason: str
    confidence: float     # 0..1

    def to_dict(self) -> dict:
        return asdict(self)


def new_signal_id() -> str:
    return "sig_" + uuid.uuid4().hex[:20]
