"""Admin-First ops config — sanitize / guardrails / store roundtrip."""

from __future__ import annotations

from pathlib import Path

from backend.ops_config import (
    DEFAULT_PRICEBOARD_OPS,
    HARD_MAX_CORE_TOTAL,
    effective_priceboard_ops,
    sanitize_priceboard_ops,
)


def test_defaults_allocation_300():
    assert DEFAULT_PRICEBOARD_OPS["core_allocation"]["HOSE"] == 160
    assert DEFAULT_PRICEBOARD_OPS["core_allocation"]["HNX"] == 80
    assert DEFAULT_PRICEBOARD_OPS["core_allocation"]["UPCOM"] == 60
    assert DEFAULT_PRICEBOARD_OPS["max_core"] == 300


def test_sanitize_clamps_over_hard_max():
    safe, warnings = sanitize_priceboard_ops(
        {
            "core_allocation": {"HOSE": 900, "HNX": 900, "UPCOM": 900},
            "max_core": 9999,
            "min_volume": -1,
        }
    )
    total = sum(safe["core_allocation"].values())
    assert total <= HARD_MAX_CORE_TOTAL
    assert safe["max_core"] <= HARD_MAX_CORE_TOTAL
    assert safe["min_volume"] >= 0
    assert warnings


def test_sanitize_invalid_number_falls_back():
    base = dict(DEFAULT_PRICEBOARD_OPS)
    safe, warnings = sanitize_priceboard_ops({"min_volume": "abc"}, base=base)
    assert safe["min_volume"] == base["min_volume"]
    assert warnings


def test_effective_from_overlay():
    ops = effective_priceboard_ops(
        {"priceboard": {"core_allocation": {"HOSE": 100, "HNX": 50, "UPCOM": 50}, "max_core": 200}}
    )
    assert ops["core_allocation"]["HOSE"] == 100
    assert ops["max_core"] == 200


def test_put_ops_config_roundtrip(tmp_path: Path, monkeypatch):
    pytest = __import__("pytest")
    try:
        import backend.admin_config_store as store
    except ModuleNotFoundError as exc:
        pytest.skip(f"deps missing on host: {exc}")

    path = tmp_path / "admin_runtime_config.json"
    monkeypatch.setattr(store, "DEFAULT_OVERLAY", path)
    monkeypatch.setattr(
        "backend.core_symbols_builder.build_core_symbols",
        lambda **_k: {"ok": True, "count": 0, "allocation": {}},
    )
    import backend.market_catalog as mc

    monkeypatch.setattr(mc, "clear_catalog_cache", lambda: None)

    out = store.put_ops_config(
        {
            "config": {
                "core_allocation": {"HOSE": 160, "HNX": 80, "UPCOM": 60},
                "max_core": 300,
                "min_volume": 100000,
                "min_volume_by_exchange": {"HOSE": 100000, "HNX": 10000, "UPCOM": 10000},
                "maintenance_mode": False,
                "ondemand_sync_enabled": True,
            }
        },
        overlay_path=path,
    )
    assert out["ok"] is True
    assert out["config"]["min_volume"] == 100000
    assert out["config"]["core_allocation"]["HOSE"] == 160
    got = store.get_ops_config(overlay_path=path)
    assert got["config"]["min_volume_by_exchange"]["HNX"] == 10000
