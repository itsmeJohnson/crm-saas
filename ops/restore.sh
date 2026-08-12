#!/usr/bin/env bash
# ── Restore a CRM backup ───────────────────────────────────────────────────
# DANGER: overwrites the target database. By default restores into a SEPARATE
# database ('crm_restore') so you can inspect it first, NOT over live 'crm'.
#
# Inspect a backup safely (default):
#   ops/restore.sh /opt/backups/crm/crm-2026-08-12-0305.sql.gz
#
# Overwrite LIVE 'crm' (only after stopping the backend; last resort):
#   CRM_RESTORE_TARGET=crm CRM_RESTORE_CONFIRM=yes ops/restore.sh <file>
set -euo pipefail

FILE="${1:?Usage: ops/restore.sh <backup.sql.gz>}"
TARGET="${CRM_RESTORE_TARGET:-crm_restore}"
DB_CONTAINER="${CRM_DB_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -iE 'postgres' | head -1)}"
DB_USER="${CRM_DB_USER:-$(docker exec "${DB_CONTAINER}" printenv POSTGRES_USER 2>/dev/null || echo postgres)}"

if [ "${TARGET}" = "crm" ] && [ "${CRM_RESTORE_CONFIRM:-no}" != "yes" ]; then
  echo "Refusing to overwrite live 'crm' without CRM_RESTORE_CONFIRM=yes. Aborting." >&2
  exit 1
fi

echo "[restore] target DB: ${TARGET} (container ${DB_CONTAINER}) from ${FILE}"
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -c "DROP DATABASE IF EXISTS ${TARGET};"
docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -c "CREATE DATABASE ${TARGET};"
gunzip -c "${FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${TARGET}"
echo "[restore] Done. Inspect with: docker exec -it ${DB_CONTAINER} psql -U ${DB_USER} -d ${TARGET}"
