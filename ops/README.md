# Ops runbook — deploy safely without losing data

Production runs on the VPS at `/opt/apps/crm` via Docker Compose. The database
lives in a Docker volume, so **rebuilding the code containers never touches your
data** — the only things that destroy data are `docker compose down -v`,
`docker volume rm`, manual `DROP`/`DELETE`, or a bad migration. Guard those.

## Backups  (`ops/backup.sh`)
Gzipped `pg_dump` with integrity check + 14‑day retention → `/opt/backups/crm/`.
Auto‑detects the Postgres container and its user/db.

- Runs automatically **daily at 03:05** via cron, and **before every deploy** (see below).
- **Set up off‑site copies** (S3 / Backblaze / rclone) — a backup on the same VPS
  is not a backup. Uncomment the off‑site line at the bottom of `ops/backup.sh`.
- Restore/inspect a backup safely (into a separate DB, never over live by default):
  ```bash
  ops/restore.sh /opt/backups/crm/crm-YYYY-MM-DD-HHMMSS.sql.gz
  ```

## Deploying  (`ops/deploy.sh`)
```
backup  →  git pull  →  rebuild+restart  →  alembic upgrade head  →  health check
```
```bash
cd /opt/apps/crm && ./ops/deploy.sh            # backend + frontend
cd /opt/apps/crm && ./ops/deploy.sh backend    # backend only
```
If the health check fails, roll back:
```bash
git log --oneline -5           # find the last good commit/tag
git checkout <commit-or-tag>
docker compose up -d --build backend frontend
```
**Tag every release** so rollback is trivial: `git tag v1.4.0 && git push --tags`.

## Schema changes (migrations)
Production is Alembic‑tracked. **Never change a DB column by editing a model alone**
— on existing tables `create_all` does NOT add columns, so the column silently
won't exist in prod. Instead:

1. `ops/new-migration.sh "what changed"`
2. Edit the file in `backend/alembic/versions/`. Use **idempotent DDL** because the
   schema has some historical drift (e.g. `plans.promo_price` exists in prod but not
   in the chain):
   ```python
   def upgrade():
       op.execute("ALTER TABLE contacts ADD COLUMN IF NOT EXISTS loyalty_points INT DEFAULT 0")
   def downgrade():
       op.execute("ALTER TABLE contacts DROP COLUMN IF EXISTS loyalty_points")
   ```
3. Commit + `ops/deploy.sh` (it runs `alembic upgrade head`).

Do **not** use `alembic revision --autogenerate` until the drift is reconciled —
it will emit `add_column` for things that already exist and fail on prod.

**Golden rule for live data — expand → migrate → contract:** add columns nullable,
deploy code that uses them, backfill, and only remove old columns in a *later*
release. Never rename/drop in the same deploy as the code change.

## Recommended next hardening (not yet done)
- Switch prod to `docker-compose.prod.yml` + `Dockerfile.prod` + `backend/entrypoint.sh`
  (migrate‑then‑start, real uvicorn workers, production frontend build) and set
  `RUN_CREATE_ALL=false` so migrations become the single source of truth.
- Stand up a **staging** stack (separate DB) to test before prod.
- Rotate the shared JWT/DB secrets out of `docker-compose.yml` into a `.env`.
