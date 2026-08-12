#!/usr/bin/env bash
# ── CRM Postgres backup ────────────────────────────────────────────────────
# Dumps the CRM database from the running Postgres container, gzips it, checks
# integrity, and prunes old backups. Safe to run anytime (read-only on the DB).
#
# Usage:   ops/backup.sh
# Cron:    5 3 * * *  cd /opt/apps/crm && ./ops/backup.sh >> /opt/backups/crm/backup.log 2>&1
#
# Overridable via env:
#   CRM_BACKUP_DIR         (default /opt/backups/crm)
#   CRM_BACKUP_RETAIN_DAYS (default 14)
#   CRM_DB_CONTAINER       (default: auto-detect the postgres container)
#   CRM_DB_USER            (default postgres)
#   CRM_DB_NAME            (default crm)
set -euo pipefail

BACKUP_DIR="${CRM_BACKUP_DIR:-/opt/backups/crm}"
RETAIN_DAYS="${CRM_BACKUP_RETAIN_DAYS:-14}"
DB_USER="${CRM_DB_USER:-postgres}"
DB_NAME="${CRM_DB_NAME:-crm}"
DB_CONTAINER="${CRM_DB_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -iE '(^|[-_])postgres$|(^|[-_])postgres' | head -1)}"

if [ -z "${DB_CONTAINER}" ]; then
  echo "[backup] ERROR: could not find a running postgres container. Set CRM_DB_CONTAINER." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
TS="$(date +%F-%H%M%S)"
FILE="${BACKUP_DIR}/crm-${TS}.sql.gz"

echo "[backup] $(date '+%F %T') dumping '${DB_NAME}' from container '${DB_CONTAINER}' -> ${FILE}"
# pg_dump | gzip; pipefail makes a pg_dump failure fail the whole pipeline.
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${FILE}"

# Integrity: gzip must be valid and the file non-trivial.
gzip -t "${FILE}"
SIZE="$(stat -c%s "${FILE}" 2>/dev/null || stat -f%z "${FILE}")"
if [ "${SIZE}" -lt 1000 ]; then
  echo "[backup] ERROR: backup only ${SIZE} bytes — likely failed. Removing." >&2
  rm -f "${FILE}"
  exit 1
fi

# Prune old backups.
find "${BACKUP_DIR}" -name 'crm-*.sql.gz' -type f -mtime "+${RETAIN_DAYS}" -delete 2>/dev/null || true

echo "[backup] OK ${FILE} (${SIZE} bytes). Retained last ${RETAIN_DAYS} days."
# ── OFF-SITE (recommended): uncomment and configure one of these ────────────
# aws s3 cp "${FILE}" "s3://your-bucket/crm-backups/" --only-show-errors
# rclone copy "${FILE}" "remote:crm-backups/"
