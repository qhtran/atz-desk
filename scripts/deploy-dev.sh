#!/usr/bin/env bash
# Deploy ATZ Desk dev (SSH → VPS). Chạy từ thư mục gốc repo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${ROOT}/scripts/deploy-vps.sh" dev "$@"
