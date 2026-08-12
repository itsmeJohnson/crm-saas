#!/usr/bin/env bash
# ── Safe production deploy ─────────────────────────────────────────────────
# 1. Back up the database (so any deploy is recoverable)
# 2. Pull the latest code (fast-forward only)
# 3. Rebuild + restart the given services (default: backend frontend)
# 4. Wait for the backend health check; report clearly
#
# Usage:  ops/deploy.sh                 # deploys backend + frontend
#         ops/deploy.sh backend         # just the backend
#
# Rollback (if a deploy goes bad):
#   git log --oneline -5           # find the previous good commit/tag
#   git checkout <commit-or-tag>
#   docker compose up -d --build backend frontend
set -euo pipefail

REPO_DIR="${CRM_REPO_DIR:-/opt/apps/crm}"
SERVICES=("$@")
if [ "${#SERVICES[@]}" -eq 0 ]; then SERVICES=(backend frontend); fi

cd "${REPO_DIR}"

echo "==> [1/4] Backup before deploy"
./ops/backup.sh

echo "==> [2/4] Pull latest code"
git pull --ff-only

echo "==> [3/4] Rebuild + restart: ${SERVICES[*]}"
docker compose up -d --build "${SERVICES[@]}"

echo "==> [4/4] Waiting for backend health…"
ok=0
for i in $(seq 1 20); do
  if docker exec crm-backend python -c "import httpx,asyncio
async def go():
    async with httpx.AsyncClient() as c:
        r=await c.get('http://localhost:8000/api/v1/health'); print(r.status_code)
asyncio.run(go())" 2>/dev/null | grep -q 200; then ok=1; break; fi
  sleep 3
done

if [ "${ok}" -eq 1 ]; then
  echo "==> ✅ Deploy healthy."
  docker compose ps
else
  echo "==> ❌ Backend did not become healthy. Check: docker logs crm-backend --tail 50"
  echo "    Roll back with: git checkout <previous> && docker compose up -d --build backend frontend"
  exit 1
fi
