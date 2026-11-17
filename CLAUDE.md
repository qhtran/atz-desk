# CLAUDE / agent guide — atz-desk

Active scope: **dev.atz.vn** (`backend/`, `frontend/`, `docker-compose.dev.yml`).

## Hard constraints (máy chặn)

Đã chuyển sang **Ruff + GitHub Actions** — agent/PR **không được** bỏ qua:

| Luật | Enforce |
|---|---|
| Không `print()` debug trong library `backend/` (CLI seed được ignore có chủ đích) | Ruff `T20` |
| Unused import / undefined name | Ruff `F401` / `F821` (+ `E9`/`F7`/`F82`) |
| Cấm import legacy `src` / `src.atz` từ `backend/` + `tests/` | Ruff `TID251` |
| Không đưa `.env*`, `.pip_index`, `*.key`/`.pem` vào PR | `scripts/ci_secret_guard.sh` trong CI |
| Lint/test fail → CI đỏ | `docs/ci/github-actions-ci.yml` (copy → `docs/ci/github-actions-ci.yml → .github/workflows/ci.yml` khi PAT có `workflow` scope) |

Chạy local:

```bash
pip install -r requirements-dev.txt
ruff check backend tests
PYTHONPATH=. pytest -q tests/test_pwa_assets.py tests/test_logging_middleware.py tests/test_tick_contract.py
```

## Judgment-only (prose — máy không kiểm hết)

Giữ trong `.cursorrules` + `.cursor/rules/*` + `AGENTS.md`:

1. **Hỏi xác nhận** trước khi sửa code; kế hoạch ngắn trước.
2. **Một module / một lần**; không abstraction sớm; giữ pattern hiện có.
3. **Token deny-list**: không quét full repo; luôn `path`/`glob` hẹp; không đụng path trong `.cursorignore` trừ khi user @.
4. Mọi phản hồi agent: dòng **`[DBG]`** + lựa chọn số `1a`/`1b` khi hỏi.
5. **Không** đụng `src/atz/` (prod) trừ khi user yêu cầu rõ.
6. **Không** sửa nginx / Authentik / SSH / firewall trừ khi được yêu cầu rõ.
7. Đổi kiến trúc/API/contract → ghi `docs/TECH_JOURNAL.md`.
8. Config trong `config/*.yaml`; không commit secret; trả lời tiếng Việt ngắn.

Chi tiết hành vi agent: `.cursor/rules/token-scope.mdc`, `dev-atz-scope.mdc`, `debug-tags.mdc`, `karpathy-workflow.mdc`, `atz.mdc`, `tech-journal.mdc`.
