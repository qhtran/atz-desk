# Task T-hdtl-depth-p1-prep — HĐTL depth UX (P1 prep)

**Owner:** ag2  
**Status:** Done (chờ master_ack)  
**Phạm vi:** dev.atz.vn

## Mục tiêu

Chuẩn bị pipeline depth thật cho **VN30F1M/F2M**: partial tick WS, publish merge, FE không fake khi đã có depth SSI (ngoài giờ, chưa capture schema phiên).

## File được sửa

- `backend/board_universe.py` — `FUTURES_SYMBOL_SET`
- `backend/tick_contract.py` — kind HĐTL + `tick_has_payload`
- `backend/ssi_live.py` — publish partial depth
- `frontend/index.html` — `enrichDepth` partial WS depth
- `tests/test_tick_contract.py`

## DoD

- [x] VN30F1M X-Quote parse `kind=equity`, depth không cần `last`
- [x] Publish tick equity depth-only (`tick_has_payload`)
- [x] FE: partial SSI depth → `symbolsWithServerDepth`, không fake
- [x] pytest Pass — `python3 -m pytest tests/test_tick_contract.py tests/test_board_universe.py -q` (21)

## Ngoài phạm vi

- Capture payload giờ mở cửa / điền bảng map SSI (P1 pass)
- Prod, nginx, sshd

## Spec

`docs/specs/PRICEBOARD_P1_DEPTH_NN.md` §3 partial tick, §5 FE gate
