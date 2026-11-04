#!/usr/bin/env bash
# Backup an toàn các SQLite Desk (online `.backup`) → tar.gz theo ngày.
#
# Mặc định:
#   DATA_DIR=/opt/atz-desk/data
#   BACKUP_ROOT=/var/backups/atz-desk
#   RETENTION_DAYS=7
#
# Ví dụ:
#   ./scripts/backup_db.sh
#   DATA_DIR=./data BACKUP_ROOT=./backups RETENTION_DAYS=7 ./scripts/backup_db.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${DATA_DIR:-${ROOT}/data}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/atz-desk}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
STAMP="${BACKUP_STAMP:-$(date +%Y-%m-%d)}"
# Danh sách DB ưu tiên (CDA); bỏ qua nếu file không tồn tại.
DB_NAMES=(
  desk_alerts.db
  desk_portfolio.db
  market.db
)

log() {
  printf '[backup_db] %s\n' "$*"
}

die() {
  printf '[backup_db] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 not found (apt install sqlite3)"
command -v tar >/dev/null 2>&1 || die "tar not found"

mkdir -p "${BACKUP_ROOT}"
WORKDIR="$(mktemp -d "${BACKUP_ROOT}/.tmp-XXXXXX")"
cleanup() {
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT

log "DATA_DIR=${DATA_DIR}"
log "BACKUP_ROOT=${BACKUP_ROOT}"
log "STAMP=${STAMP}"

backed=()
missing=()
for name in "${DB_NAMES[@]}"; do
  src="${DATA_DIR}/${name}"
  if [[ ! -f "${src}" ]]; then
    missing+=("${name}")
    log "skip missing ${src}"
    continue
  fi
  dest="${WORKDIR}/${name%.db}-${STAMP}.db"
  log "sqlite3 .backup → ${dest}"
  # Online-safe snapshot (không copy file khi DB đang mở).
  if ! sqlite3 "${src}" ".backup '${dest}'"; then
    die "sqlite3 .backup failed for ${src}"
  fi
  # integrity quick check
  if ! sqlite3 "${dest}" "PRAGMA integrity_check;" | grep -qx "ok"; then
    die "integrity_check failed for ${dest}"
  fi
  backed+=("$(basename "${dest}")")
done

if [[ ${#backed[@]} -eq 0 ]]; then
  die "no databases backed up (looked in ${DATA_DIR}: ${DB_NAMES[*]})"
fi

ARCHIVE="${BACKUP_ROOT}/atz-desk-sqlite-${STAMP}.tar.gz"
log "tar → ${ARCHIVE}"
tar -C "${WORKDIR}" -czf "${ARCHIVE}.partial" "${backed[@]}"
mv -f "${ARCHIVE}.partial" "${ARCHIVE}"
chmod 640 "${ARCHIVE}" || true

log "wrote ${ARCHIVE} ($(du -h "${ARCHIVE}" | awk '{print $1}')) files=${backed[*]}"
if [[ ${#missing[@]} -gt 0 ]]; then
  log "missing (ok): ${missing[*]}"
fi

# Xóa archive cũ hơn RETENTION_DAYS.
if [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] && [[ "${RETENTION_DAYS}" -gt 0 ]]; then
  log "prune archives older than ${RETENTION_DAYS}d under ${BACKUP_ROOT}"
  find "${BACKUP_ROOT}" -maxdepth 1 -type f -name 'atz-desk-sqlite-*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete || true
fi

log "done"
