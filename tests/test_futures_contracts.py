"""HĐTL board ↔ SSI contract map."""

from backend.futures_contracts import (
    invert_contract_map,
    load_futures_contract_map,
    looks_like_vn30_futures_contract,
    parse_futures_contracts_env,
)


def test_default_map_has_both_front_months():
    m = load_futures_contract_map()
    assert m["VN30F1M"].startswith("41I1")
    assert m["VN30F2M"].startswith("41I1")
    assert m["VN30F1M"] != m["VN30F2M"]


def test_yaml_and_env_override(monkeypatch):
    monkeypatch.setenv("PRICEBOARD_FUTURES_CONTRACTS", "VN30F1M:41I1ZZ000")
    m = load_futures_contract_map({"futures_contracts": {"VN30F2M": "41I1YY000"}})
    assert m["VN30F1M"] == "41I1ZZ000"
    assert m["VN30F2M"] == "41I1YY000"


def test_parse_env_and_invert():
    m = parse_futures_contracts_env("VN30F1M:41I1GB000, VN30F2M:41I1GC000")
    assert invert_contract_map(m)["41I1GB000"] == "VN30F1M"
    assert looks_like_vn30_futures_contract("41I1GB000")
    assert not looks_like_vn30_futures_contract("VN30F1M")
    assert not looks_like_vn30_futures_contract("FPT")
