"""Evaluator: timeout 2s/filter, cô lập lỗi, filter circuit (lỗi liên tục -> tạm disable)."""
from __future__ import annotations

import logging
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from filter_runner.log import ERR_DISABLED, ERR_EXCEPTION, ERR_TIMEOUT, log


class FilterCircuit:
    def __init__(self, threshold: int, window: float, disable_seconds: float, clock=time.monotonic):
        self.threshold, self.window, self.disable_for, self.clock = threshold, window, disable_seconds, clock
        self.failures: dict[str, deque] = {}
        self.disabled_until: dict[str, float] = {}

    def is_disabled(self, name: str) -> bool:
        until = self.disabled_until.get(name)
        if until is None:
            return False
        if self.clock() >= until:
            del self.disabled_until[name]
            self.failures.pop(name, None)
            log("CIRCUIT", f"filter re-enabled after {self.disable_for:.0f}s", filter_name=name, circuit_state="CLOSED")
            return False
        return True

    def disabled(self) -> list[str]:
        return [n for n in list(self.disabled_until) if self.is_disabled(n)]

    def success(self, name: str) -> None:
        self.failures.pop(name, None)

    def failure(self, name: str) -> None:
        now = self.clock()
        q = self.failures.setdefault(name, deque())
        q.append(now)
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.threshold:
            self.disabled_until[name] = now + self.disable_for
            q.clear()
            log("CIRCUIT", f"filter disabled for {self.disable_for:.0f}s after {self.threshold} failures within {self.window:.0f}s",
                logging.ERROR, error_code=ERR_DISABLED, filter_name=name, circuit_state="OPEN")


class Evaluator:
    def __init__(self, timeout: float, workers: int, circuit: FilterCircuit):
        self.timeout, self.circuit = timeout, circuit
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="filter-eval")

    def run(self, name: str, fn, bars, symbol: str, cache_key=None, memo=None):
        """Trả SignalResult hoặc None (lỗi/timeout/disabled). memo: tránh chạy lại cùng filter+params cho nhiều user."""
        if memo is not None and cache_key in memo:
            return memo[cache_key]
        if self.circuit.is_disabled(name):
            log("EVAL", "skip: filter temporarily disabled", logging.WARNING, error_code=ERR_DISABLED,
                symbol=symbol, filter_name=name, circuit_state="OPEN")
            return None
        started = time.monotonic()
        future = self.pool.submit(fn, bars)
        result = None
        try:
            result = future.result(timeout=self.timeout)
            self.circuit.success(name)
        except FutureTimeout:
            future.cancel()
            log("EVAL", f"filter evaluate timeout > {self.timeout}s", logging.ERROR, error_code=ERR_TIMEOUT,
                symbol=symbol, filter_name=name, latency_ms=int((time.monotonic() - started) * 1000))
            self.circuit.failure(name)
        except Exception as error:  # noqa: BLE001 - cô lập mọi lỗi của filter
            log("EVAL", f"filter exception isolated: {type(error).__name__}: {str(error)[:200]}", logging.ERROR,
                error_code=ERR_EXCEPTION, symbol=symbol, filter_name=name,
                latency_ms=int((time.monotonic() - started) * 1000))
            self.circuit.failure(name)
        if memo is not None:
            memo[cache_key] = result
        return result
