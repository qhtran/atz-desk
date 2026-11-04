"""On-demand Redis touch + idle prune (no live SSI)."""

from __future__ import annotations

from backend.market_catalog import clear_catalog_cache, load_core_symbol_set
from backend.ondemand_watch import list_active_ondemand, touch_ondemand_symbols


class _FakeRedis:
    def __init__(self) -> None:
        self.h: dict[str, str] = {}

    def hgetall(self, _key: str) -> dict[str, str]:
        return dict(self.h)

    def hset(self, _key: str, field: str, value: str) -> None:
        self.h[str(field)] = str(value)

    def hdel(self, _key: str, field: str) -> None:
        self.h.pop(str(field), None)

    def hlen(self, _key: str) -> int:
        return len(self.h)

    def close(self) -> None:
        return None


def setup_function() -> None:
    clear_catalog_cache()


def test_touch_skips_core_and_tracks_offcore():
    core = load_core_symbol_set()
    assert "FPT" in core
    # Pick a symbol almost certainly outside core; if DBC is now in Top240, use ZZZTEST
    off = "ZZZTEST"
    assert off not in core
    client = _FakeRedis()
    out = touch_ondemand_symbols(
        ["FPT", off],
        client=client,  # type: ignore[arg-type]
        now=1_000.0,
        idle_sec=60,
        max_symbols=40,
    )
    assert out["ok"] is True
    assert "FPT" in out["skipped_core"]
    assert off in out["touched"]
    assert client.h.get(off) == "1000.0"
    active = list_active_ondemand(client=client, now=1_010.0, idle_sec=60)  # type: ignore[arg-type]
    assert active == [off]


def test_idle_expiry_prunes():
    client = _FakeRedis()
    touch_ondemand_symbols(
        ["ZZZIDLE"],
        client=client,  # type: ignore[arg-type]
        now=100.0,
        idle_sec=30,
        max_symbols=40,
        skip_core=False,
    )
    assert list_active_ondemand(client=client, now=140.0, idle_sec=30) == []  # type: ignore[arg-type]
