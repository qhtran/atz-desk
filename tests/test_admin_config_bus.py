"""Admin config Redis reload bus + stream listener handler."""

from __future__ import annotations

import json

from backend.admin_config_bus import build_reload_message, config_reload_channel
from backend.engine.stream_listener import QuantStreamListener
from backend.websocket_manager import ConnectionManager


def test_config_reload_channel_default():
    assert config_reload_channel() == "admin:config-reload"


def test_build_reload_message_includes_stream():
    raw = build_reload_message({"rsi": {"oversold": 25}})
    payload = json.loads(raw)
    assert payload["type"] == "config_reload"
    assert payload["stream_alerts"]["rsi"]["oversold"] == 25
    assert payload["channel"] == "admin:config-reload"


def test_stream_listener_handles_config_reload_payload():
    listener = QuantStreamListener(ConnectionManager(), cfg={"rsi": {"oversold": 30}, "enabled": True})
    msg = build_reload_message({"rsi": {"oversold": 19, "overbought": 80}, "volume_spike": {"mult": 2.5}})
    listener._handle_config_reload_message(msg)
    assert listener._cfg["rsi"]["oversold"] == 19
    assert listener._cfg["volume_spike"]["mult"] == 2.5
