#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: ops/build-protected-images.sh
# PURPOSE: Builds protected Docker images (Cython-compiled binary backend +
#          minified frontend), pushes them to your private registry, and packages
#          the client deployment bundle (ZERO source code included).
# ==============================================================================
set -euo pipefail

REGISTRY="${CRM_IMAGE_REGISTRY:-ghcr.io/johnsonsoftwares}"
TAG="${CRM_IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"
OUTPUT_BUNDLE="client-deployment-bundle.tar.gz"

echo "======================================================================"
echo " Building Protected Images for Client Deployment"
echo " Registry: ${REGISTRY}"
echo " Tag:      ${TAG}"
echo "======================================================================"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# 1. Build Cythonized Backend Image (compiles .py into .so, deletes .py)
echo "==> [1/4] Building Cythonized Backend Image (Zero Python Source Code)..."
docker build \
  -f backend/Dockerfile.cython \
  -t "${REGISTRY}/crm-backend:${TAG}" \
  -t "${REGISTRY}/crm-backend:latest" \
  backend

# 2. Build Minified Production Frontend Image
echo "==> [2/4] Building Production Frontend Image..."
docker build \
  -f frontend/Dockerfile \
  -t "${REGISTRY}/crm-frontend:${TAG}" \
  -t "${REGISTRY}/crm-frontend:latest" \
  frontend

# 3. Optional Push to Private Container Registry
read -p "Do you want to push these images to ${REGISTRY} now? (y/N): " -r CONFIRM || CONFIRM="n"
if [[ "${CONFIRM}" =~ ^[Yy]$ ]]; then
  echo "==> [3/4] Pushing images to ${REGISTRY}..."
  docker push "${REGISTRY}/crm-backend:${TAG}"
  docker push "${REGISTRY}/crm-backend:latest"
  docker push "${REGISTRY}/crm-frontend:${TAG}"
  docker push "${REGISTRY}/crm-frontend:latest"
else
  echo "==> [3/4] Skipping registry push. Images tagged locally."
fi

# 4. Generate Client Distribution Package (Only Compose + Env + Setup Script)
echo "==> [4/4] Generating Client VPS Deployment Bundle: ${OUTPUT_BUNDLE}..."
TMP_DIR="$(mktemp -d)"
mkdir -p "${TMP_DIR}/bundle/nginx/conf.d"

# Copy compose and env templates
cp docker-compose.client-vps.yml "${TMP_DIR}/bundle/docker-compose.yml"
cp .env.client.example "${TMP_DIR}/bundle/.env.example"

# Generate Client Launch Script
cat << 'EOF' > "${TMP_DIR}/bundle/launch.sh"
#!/usr/bin/env bash
set -e
echo "======================================================================"
echo " CRM Enterprise — Client Dedicated VPS Launch Script"
echo "======================================================================"

if [ ! -f .env ]; then
  echo "Error: .env file missing! Copying .env.example to .env..."
  cp .env.example .env
  echo "Please edit .env with your domain, credentials and license key first."
  exit 1
fi

echo "Pulling latest application images from registry..."
docker compose pull

echo "Starting CRM services (Database, Redis, Backend, Frontend)..."
docker compose up -d

echo "Running database migrations..."
docker compose exec -T backend alembic upgrade head

echo ""
echo "✅ CRM has been launched successfully!"
echo "Check container status with: docker compose ps"
echo "Check backend logs with:     docker compose logs -f backend"
EOF
chmod +x "${TMP_DIR}/bundle/launch.sh"

tar -czf "${OUTPUT_BUNDLE}" -C "${TMP_DIR}/bundle" .
rm -rf "${TMP_DIR}"

echo ""
echo "======================================================================"
echo " SUCCESS! Client bundle created: ${OUTPUT_BUNDLE}"
echo " You can now send '${OUTPUT_BUNDLE}' to the telecalling agency."
echo " Their VPS will run the CRM without ever accessing your source code."
echo "======================================================================"
