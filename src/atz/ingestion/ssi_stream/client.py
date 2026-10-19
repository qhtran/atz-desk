"""WebSocket client SSI Market DATA — reconnect + PONG + SUBSCRIBE."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from ingestion.log import log as _log

try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore


def log(action: str, message: str, level: int = 20, **kw) -> None:
    _log("SSI-STREAM-" + action, message, level, **kw)


ERR_WS = "ERR-SSISTREAM-001"
ERR_AUTH = "ERR-SSISTREAM-002"
ERR_PARSE = "ERR-SSISTREAM-003"


class SsiStreamClient:
    """Chạy blocking run_forever trong thread; main loop giám sát health/reconnect."""

    def __init__(
        self,
        url: str,
        topics: list[str],
        token_provider: Callable[[], str],
        on_message: Callable[[dict], None],
        on_state: Callable[[str, dict], None] | None = None,
        auth_payload: dict | None = None,
    ):
        if websocket is None:
            raise RuntimeError("websocket-client package missing")
        self.url = url
        self.topics = topics
        self.token_provider = token_provider
        self.on_message = on_message
        self.on_state = on_state or (lambda *_: None)
        self.auth_payload = auth_payload or {}
        self._ws = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_msg_at = 0.0
        self.connected = False
        self.msg_count = 0
        self.err_count = 0

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ssi-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:  # noqa: BLE001
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                token = self.token_provider()
            except Exception as err:  # noqa: BLE001
                self.err_count += 1
                log("AUTH", f"token failed: {err}", logging.ERROR, error_code=ERR_AUTH)
                self.on_state("auth_fail", {"error": str(err)[:160]})
                self._stop.wait(5)
                continue
            headers = [f"Authorization: Bearer {token}"]
            self._ws = websocket.WebSocketApp(
                self.url,
                header=headers,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )
            self.on_state("connecting", {"url": self.url})
            try:
                self._ws.run_forever(ping_interval=0, ping_timeout=None)
            except Exception as err:  # noqa: BLE001
                self.err_count += 1
                log("WS", f"run_forever error: {err}", logging.ERROR, error_code=ERR_WS)
            self.connected = False
            if self._stop.is_set():
                break
            self.on_state("disconnected", {})
            self._stop.wait(1)

    def _on_open(self, ws) -> None:
        self.connected = True
        self.last_msg_at = time.time()
        # Header Bearer thường đủ; một số bản SSI còn nhận JSON auth sau open.
        body = {k: v for k, v in self.auth_payload.items() if v}
        if body:
            try:
                try:
                    body = {**body, "access_token": self.token_provider()}
                except Exception:  # noqa: BLE001
                    pass
                ws.send(json.dumps(body))
            except Exception as err:  # noqa: BLE001
                log("WS", f"auth body send skip: {err}", logging.WARNING)
        sub = {"method": "SUBSCRIBE", "channel": "DATA", "topics": self.topics}
        try:
            ws.send(json.dumps(sub))
            log("WS", f"subscribed n={len(self.topics)}")
            self.on_state("subscribed", {"topics": len(self.topics)})
        except Exception as err:  # noqa: BLE001
            self.err_count += 1
            log("WS", f"subscribe failed: {err}", logging.ERROR, error_code=ERR_WS)

    def _on_message(self, ws, message: str) -> None:
        self.last_msg_at = time.time()
        self.msg_count += 1
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            log("PARSE", f"non-json len={len(message)}", logging.WARNING, error_code=ERR_PARSE)
            return
        if not isinstance(data, dict):
            return
        method = str(data.get("method") or "").upper()
        channel = str(data.get("channel") or "").upper()
        if method == "PING" or channel == "HEARTBEAT" and method != "PONG":
            try:
                ws.send(json.dumps({
                    "method": "PONG",
                    "channel": "HEARTBEAT",
                    "time": data.get("time") or time.strftime("%d-%m-%Y %H-%M-%S"),
                }))
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            self.on_message(data)
        except Exception as err:  # noqa: BLE001
            self.err_count += 1
            log("PARSE", f"handler: {type(err).__name__}: {err}", logging.WARNING, error_code=ERR_PARSE)

    def _on_error(self, ws, error) -> None:
        self.err_count += 1
        log("WS", f"error: {error}", logging.WARNING, error_code=ERR_WS)
        self.on_state("error", {"error": str(error)[:160]})

    def _on_close(self, ws, status_code, msg) -> None:
        self.connected = False
        log("WS", f"closed code={status_code} msg={msg}")
        self.on_state("closed", {"code": status_code})
