"""Signal Publisher: XADD stream:signals (maxlen)."""
from __future__ import annotations

from filter_runner.contracts import Signal
from filter_runner.log import log


class SignalPublisher:
    def __init__(self, redis_client, stream: str, maxlen: int):
        self.r, self.stream, self.maxlen = redis_client, stream, maxlen

    def publish(self, signal: Signal) -> str:
        fields = {k: str(v) for k, v in signal.to_dict().items()}
        entry = self.r.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)
        log("SIGNAL", f"published {signal.direction} {signal.filter_name} stream={self.stream} id={entry}",
            symbol=signal.symbol, user_id=signal.user_id, signal_id=signal.signal_id,
            filter_name=signal.filter_name, confidence=signal.confidence)
        return entry
