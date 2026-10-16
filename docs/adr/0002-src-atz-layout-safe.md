# ADR 0002: src/atz layout (1d-safe) — implemented

- **Status:** Accepted / Done (P1–P3)
- **Date:** 2026-10-17
- **Decision:** Move Python packages under `src/atz/`, keep package names (`ingestion`, `ui`, …). Set `PYTHONPATH=/app/src/atz` (Docker) and `pytest.ini pythonpath = src/atz`. YAML stays at repo `config/`. Paths via `storage.paths.repo_root()`.
- **Not done (deferred):** rename to `atz.services.*` / domain-adapters split.
