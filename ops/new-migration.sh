#!/usr/bin/env bash
# ── Create a new (empty) Alembic migration to edit by hand ─────────────────
# We create migrations MANUALLY rather than with --autogenerate, because the
# prod schema has historically drifted from the migration chain (columns added
# via create_all without a migration). Autogenerate would emit add_column for
# things that already exist and fail on prod. So: create empty, then write the
# upgrade()/downgrade() using idempotent DDL.
#
# Usage:  ops/new-migration.sh "add loyalty_points to contacts"
#
# Then edit the generated file under backend/alembic/versions/ and use guards:
#   op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS loyalty_points INT DEFAULT 0")
# so it is safe whether or not the column already exists on a given environment.
set -euo pipefail
MSG="${1:?Usage: ops/new-migration.sh \"short message\"}"
docker exec crm-backend alembic revision -m "${MSG}"
echo "Created. Edit it under backend/alembic/versions/, then deploy (ops/deploy.sh runs 'alembic upgrade head')."
