"""Adapter nguồn KBS / VCI: rate limit + timeout + retry có jitter + circuit breaker."""
from __future__ import annotations

import random
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from ingestion.circuit_breaker import CircuitBreaker
from ingestion.log import ERR_TIMEOUT, log
from ingestion.rate_limiter import TokenBucket


class SourceDown(Exception):
    pass


def vnstock_fetch(source: str):
    """Hàm lấy bảng giá thật qua vnstock (gói Golden đã cài trong image)."""
    def fetch(symbols):
        from vnstock import Market
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return Market().price_board(list(symbols), source=source.lower())
    return fetch


class SourceAdapter:
    _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingest-fetch")

    def __init__(self, name: str, fetch, limiter: TokenBucket, breaker: CircuitBreaker,
                 timeout: float, retries: int, backoff: float, jitter: float, sleep=time.sleep):
        self.name = name.upper()
        self.fetch_fn = fetch
        self.limiter, self.breaker = limiter, breaker
        self.timeout, self.retries = timeout, retries
        self.backoff, self.jitter, self.sleep = backoff, jitter, sleep

    def _attempt(self, symbols):
        self.limiter.acquire(self.name)
        future = self._pool.submit(self.fetch_fn, symbols)
        try:
            return future.result(timeout=self.timeout)
        except FutureTimeout as error:
            future.cancel()
            raise TimeoutError(f"timeout after {self.timeout}s") from error

    def fetch(self, symbols):
        """Trả về (frame, latency_ms). Lỗi sau mọi lần thử -> breaker.failure() và SourceDown."""
        if not self.breaker.allow():
            raise SourceDown(f"{self.name} circuit OPEN")
        last_error = None
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            try:
                frame = self._attempt(symbols)
                if frame is None or len(frame) == 0:
                    raise ValueError("empty response")
                latency = int((time.monotonic() - started) * 1000)
                self.breaker.success()
                log("FETCH", f"source={self.name} ok symbols={len(symbols)} rows={len(frame)} attempt={attempt + 1}",
                    latency_ms=latency, source=self.name, circuit_state=self.breaker.state)
                return frame, latency
            except Exception as error:  # noqa: BLE001 - mọi lỗi nguồn đều tính
                last_error = error
                log("FETCH", f"source={self.name} error attempt={attempt + 1}/{self.retries + 1}: {type(error).__name__}: {str(error)[:160]}",
                    error_code=ERR_TIMEOUT if isinstance(error, TimeoutError) else None,
                    latency_ms=int((time.monotonic() - started) * 1000), source=self.name,
                    circuit_state=self.breaker.state)
                if attempt < self.retries:
                    self.sleep(self.backoff * (2 ** attempt) + random.uniform(0, self.jitter))
        self.breaker.failure()
        raise SourceDown(f"{self.name} failed: {last_error}")
