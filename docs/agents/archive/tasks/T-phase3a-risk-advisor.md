# Task T-phase3a-risk-advisor — Phase 3A Risk + Advisor Scoring

**Owner:** ag2  
**Status:** Done  
**Phạm vi:** `config/trading_station.yaml`, `backend/core/trading_config.py`, `backend/engine/`, `backend/daily_signals.py`, `backend/main.py`, `tests/`

## Mục tiêu

Scaffold risk YAML + engine advisor vectorized 0–100 (Hướng 1); API trả `score` + `risk_meta` theo profile Authentik.

## DoD

- [x] YAML có `position_sizing` / `risk_tolerance` / `scoring_thresholds` (số null chờ Hiến)
- [x] `backend/engine/advisor_score.py` batch pandas (không for-score từng mã)
- [x] `POST /api/iboard/daily-signals` hits có `score` + `risk_meta`
- [x] pytest Pass

## Human tasks (trước khi wake Option B)

1. Điền `config/trading_station.yaml` từ spreadsheet Hiến (`position_sizing`, `%` cắt lỗ/chốt lời, `scoring_thresholds`).
2. Map username Authentik thật → `risk_tolerance.user_profiles` (`owner` / `hien`).
3. `git add` + `git commit` (gom Phase 3A **và** file Nginx Phase 2C còn pending) + `git push origin main`.
4. `./deploy-dev` trên VPS; verify SPA/WS + `/api/account/me` có `risk_meta`.

## Ngoài phạm vi

- Điền số spreadsheet thật (human); Option B realtime streaming; FE layout lớn
