#!/bin/bash
set -e

mkdir -p /opt/crm/certs /opt/crm/uploads

cat << 'EOF' > /opt/crm/docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: crm-db
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-crm_production}
      POSTGRES_USER: ${POSTGRES_USER:-crm_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-crm_user} -d ${POSTGRES_DB:-crm_production}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - crm-internal

  redis:
    image: redis:7-alpine
    container_name: crm-redis
    restart: always
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - crm-internal

  backend:
    image: crm-backend:latest
    container_name: crm-backend
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - .env
    volumes:
      - crm-uploads:/app/uploads
    networks:
      - crm-internal
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 15s
      timeout: 5s
      retries: 5

  frontend:
    image: crm-frontend:latest
    container_name: crm-frontend
    restart: always
    depends_on:
      - backend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./certs:/etc/nginx/certs:ro
    networks:
      - crm-internal

volumes:
  pgdata:
  redisdata:
  crm-uploads:

networks:
  crm-internal:
    driver: bridge
EOF

cat << 'EOF' > /opt/crm/.env
ENVIRONMENT=production
PROJECT_NAME="Samartha Sankalpa CRM"
API_V1_STR=/api/v1
FRONTEND_URL=https://crm.samarthasankalpa.com
BACKEND_CORS_ORIGINS=["https://crm.samarthasankalpa.com","http://97.74.85.190","https://97.74.85.190","http://localhost:5173","http://localhost"]

JWT_SECRET_KEY=ae2f9d1306770bc796c639620b750501fb4e47f86a5a87d19b2c0c16b6808d55
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30
TELEPHONY_ENCRYPTION_KEY=ZCZIIZBpjYWdKtUxT14q7FioS466/iw756NMMk443Cw=

POSTGRES_SERVER=postgres
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=e68b8925af051eeb52333607a1705680
POSTGRES_DB=crm_production
SQLALCHEMY_DATABASE_URI=postgresql+asyncpg://crm_user:e68b8925af051eeb52333607a1705680@postgres:5432/crm_production
RUN_CREATE_ALL=false

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=d898577d5d3676d5551402b37052824f
REDIS_URL=redis://:d898577d5d3676d5551402b37052824f@redis:6379/0

TELEPHONY_PROVIDER=myoperator
TRIAL_AUTO_APPROVE=true
EOF

chmod 600 /opt/crm/.env
chmod 644 /opt/crm/certs/*
ls -la /opt/crm
