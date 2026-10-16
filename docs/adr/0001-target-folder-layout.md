# ADR 0001: Target folder layout (scale team nhỏ)

- **Status:** Partially done — see ADR 0002 (`src/atz` + PYTHONPATH). Domain/adapters rename vẫn deferred.
- **Date:** 2026-10-17
- **Context:** Repo có hai lớp chồng nhau — realtime (ingestion → filter → alert → position → UI) và app Streamlit cũ (`analysis/`, `datasource/`, `ui/`). Root còn file hướng dẫn lẻ; không có `docs/` chuẩn.

## Decision

Chấp nhận **target layout** sau làm đích dài hạn khi onboard thêm người hoặc khi sửa lớn từng vùng. **Không** bắt buộc big-bang refactor ngay.

```text
src/atz/
  shared/      # storage, logging, errors, redis keys
  domain/      # quotes, signals, positions, filters, screening
  adapters/    # market (KBS/VCI/…), notify, auth
  services/    # ingestion, index_feed, filter_runner, alert_dispatcher, position_monitor
  web/         # Streamlit: pages + realtime (gộp ui + ui_realtime + order_helper)
docs/          # architecture, troubleshooting, ADR (phase 1 đã bắt đầu)
config/        # YAML runtime — giữ contract env
deploy/        # Authentik / infra
tests/         # map theo module/service
scripts/       # one-off, không để file lẻ ở root
```

## Consequences

- **Giữ nguyên** contract Redis/SQLite, mã `ERR-*`, Docker service names, env `INGEST_*` / …
- Migrate theo từng PR nhỏ (boy scout), có thể giữ `python -m ingestion` qua re-export tạm.
- Phase 1 (cùng đợt với ADR): chỉ dọn docs/root — không đổi package Python.

## References

- `docs/architecture.md`
- `docs/troubleshooting.md`
- `.cursor/rules/atz.mdc`
