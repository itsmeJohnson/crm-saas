# DigitalOcean Deployment Guide — Johnson Softwares CRM

> **Target:** Ubuntu 24.04 Droplet (4 GB RAM / 2 vCPU, Bangalore BLR1)
> **Referral:** https://m.do.co/c/8e992e18c3aa  (get $200 free credit)

---

## Step 1 — Create DigitalOcean Account

1. Open https://m.do.co/c/8e992e18c3aa and sign up.
2. Complete email verification and add a payment method.

---

## Step 2 — Create a Droplet

1. **Create → Droplet**
2. Region: **Bangalore (BLR1)**
3. Image: **Ubuntu 24.04 LTS x64**
4. Size: **Basic / Regular → 4 GB RAM / 2 vCPUs / 80 GB SSD** (~$24/mo)
5. Authentication: **SSH Key** — paste your Mac public key (`cat ~/.ssh/id_rsa.pub`)
6. Hostname: `crm-prod`
7. Click **Create Droplet** → note the IPv4 address (e.g. `165.22.x.x`)

---

## Step 3 — Create Managed PostgreSQL

1. **Create → Databases → PostgreSQL 16**
2. Region: **BLR1**, Plan: **Basic 1 GB** (~$15/mo)
3. After creation, go to **Connection Details** → copy the **Connection String** (URI format)
4. Under **Trusted Sources**, add your Droplet's IP.

---

## Step 4 — Create Managed Redis

1. **Create → Databases → Redis 7**
2. Region: **BLR1**, Plan: **Basic 1 GB** (~$15/mo)
3. Copy the Redis connection URI from Connection Details.
4. Under **Trusted Sources**, add your Droplet's IP.

---

## Step 5 — Create Spaces Bucket (File Storage)

1. **Create → Spaces Object Storage**
2. Region: **BLR1**
3. Name: `crm-saas-files` (must be globally unique, try `johnson-crm-files`)
4. File listing: **Restricted**
5. After creation, go to **Manage Keys** → create an Access Key.
   - Save `Access Key ID` and `Secret Access Key` — shown only once.
6. Endpoint: `https://blr1.digitaloceanspaces.com`

---

## Step 6 — Point Domain to Droplet

In Hostinger (or wherever johnsonsoftwares.com DNS is managed):

| Type | Name | Value |
|------|------|-------|
| A | @ | `<your Droplet IP>` |
| A | www | `<your Droplet IP>` |
| A | app | `<your Droplet IP>` |

Wait ~10 mins for DNS propagation before the SSL step.

---

## Step 7 — SSH into Droplet & Install Docker

```bash
ssh root@<your-droplet-ip>

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

---

## Step 8 — Add GitHub Deploy Key

```bash
# On the Droplet:
ssh-keygen -t ed25519 -C "crm-deploy" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub
```

Copy the public key output. Then in GitHub:
1. Go to https://github.com/itsmeJohnson/crm-saas → **Settings → Deploy keys**
2. **Add deploy key** → paste the public key → ✅ Allow write access → Save

Back on the Droplet:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/deploy_key
# Test:
ssh -T git@github.com
```

---

## Step 9 — Clone Repo & Set Up .env

```bash
cd /opt
git clone git@github.com:itsmeJohnson/crm-saas.git
cd crm-saas

# Copy the example env
cp .env.example .env
nano .env
```

Fill in all values in `.env`:

```env
# Database (from Step 3 — use the full URI)
DATABASE_URL=postgresql+asyncpg://doadmin:<password>@<db-host>:25060/defaultdb?ssl=require

# Redis (from Step 4)
REDIS_URL=rediss://default:<password>@<redis-host>:25061

# JWT
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>

# SMTP — Hostinger
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=465
SMTP_USER=contact@support.johnsonsoftwares.com
SMTP_PASSWORD=ItsJohnFrom@2027
SMTP_USE_TLS=true
SMTP_FROM_NAME=Johnson Softwares CRM
SMTP_FROM_EMAIL=contact@support.johnsonsoftwares.com

# Cashfree (fill in after approval)
CASHFREE_APP_ID=<your-cashfree-app-id>
CASHFREE_SECRET_KEY=<your-cashfree-secret>
CASHFREE_ENVIRONMENT=PRODUCTION

# AWS / DO Spaces (from Step 5)
AWS_ACCESS_KEY_ID=<spaces-access-key>
AWS_SECRET_ACCESS_KEY=<spaces-secret-key>
AWS_BUCKET_NAME=johnson-crm-files
AWS_REGION=blr1
AWS_ENDPOINT_URL=https://blr1.digitaloceanspaces.com

# App
BACKEND_CORS_ORIGINS=["https://app.johnsonsoftwares.com","https://johnsonsoftwares.com"]
ENVIRONMENT=production
```

---

## Step 10 — SSL Certificate (Let's Encrypt)

```bash
apt install -y certbot
certbot certonly --standalone -d app.johnsonsoftwares.com -d johnsonsoftwares.com \
  --email contact@support.johnsonsoftwares.com --agree-tos --no-eff-email

# Certs saved to:
# /etc/letsencrypt/live/app.johnsonsoftwares.com/fullchain.pem
# /etc/letsencrypt/live/app.johnsonsoftwares.com/privkey.pem

# Auto-renew (add to crontab):
(crontab -l; echo "0 3 * * * certbot renew --quiet") | crontab -
```

---

## Step 11 — Start the Application

```bash
cd /opt/crm-saas
docker compose up -d --build

# Watch logs:
docker compose logs -f backend
docker compose logs -f frontend

# Check all containers running:
docker compose ps
```

---

## Step 12 — Add GitHub Secrets for Auto-Deploy

In GitHub → **Settings → Secrets and Variables → Actions → New repository secret**:

| Secret Name | Value |
|-------------|-------|
| `DO_HOST` | `<your Droplet IP>` |
| `DO_USER` | `root` |
| `DO_SSH_KEY` | Contents of `~/.ssh/deploy_key` (private key, from Droplet) |

After adding these, every push to `main` or `demo-stable` will auto-deploy via CI/CD.

---

## Step 13 — Create Super Admin Account

```bash
# On the Droplet:
cd /opt/crm-saas
docker compose exec backend python -c "
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.auth_service import AuthService

async def create_super():
    async with AsyncSessionLocal() as db:
        svc = AuthService(db)
        user = await svc.create_super_admin(
            email='johnsondev02@gmail.com',
            password='<choose-a-strong-password>',
            full_name='DEVARAJ JOHNSON'
        )
        print(f'Super Admin created: {user.email}')

asyncio.run(create_super())
"
```

---

## Step 14 — Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

---

## Step 15 — Verify Everything Works

```bash
# Health check
curl https://app.johnsonsoftwares.com/api/v1/health

# Backend logs (no errors)
docker compose logs backend --tail=50

# Frontend accessible
open https://app.johnsonsoftwares.com
```

---

## Post-Launch Checklist

- [ ] DigitalOcean Droplet running ✅
- [ ] Managed PostgreSQL connected ✅
- [ ] Managed Redis connected ✅
- [ ] Spaces bucket created ✅
- [ ] SSL cert issued (Let's Encrypt) ✅
- [ ] DNS A records pointing to Droplet ✅
- [ ] `.env` filled in with all secrets ✅
- [ ] Super Admin account created ✅
- [ ] Cashfree credentials added (after approval) ⏳
- [ ] GitHub Actions secrets added (auto-deploy) ✅
- [ ] `certbot renew` cron configured ✅

---

## Estimated Monthly Cost (BLR1)

| Resource | Cost |
|----------|------|
| Droplet 4GB | ~$24 |
| Managed PostgreSQL 1GB | ~$15 |
| Managed Redis 1GB | ~$15 |
| Spaces 250GB | ~$5 |
| **Total** | **~$59/mo** |

> Tip: Use the $200 referral credit to run free for ~3 months.

---

## Razorpay Appeal (Secondary Gateway)

If you want Razorpay as a fallback after Cashfree approval:
1. Log into https://dashboard.razorpay.com
2. Go to **Account & Settings → Business Information**
3. Complete KYC with UDYAM certificate (UDYAM-KR-03-0427036)
4. Submit appeal with business registration proof
5. Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` to `.env` once approved
