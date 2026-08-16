#!/bin/bash
# ── Production entrypoint (application runtime only) ─────────────────────────
# WP-03A: Alembic migrations are NO LONGER run here. Schema migration is a
# separate, dedicated step executed as the crm_migrator role BEFORE the app
# starts (the `migrate` service in docker-compose.prod.yml, or `ops/deploy.sh`).
# The application runs as the unprivileged crm_runtime role and never issues DDL.
# See ops/roles/README.md.

set -e

echo "[entrypoint] Starting application server (runtime role, no migrations)..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
