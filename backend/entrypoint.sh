#!/bin/bash
# ── Production entrypoint ──────────────────────────────────────────────────
# 1. Run Alembic migrations (idempotent — safe to run on every start)
# 2. Start Uvicorn

set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting application server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
