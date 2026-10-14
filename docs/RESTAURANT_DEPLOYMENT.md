# Restaurant QR‑Voucher — Deployment & Go‑Live Runbook

The restaurant vertical ships **inside the existing CRM** (no separate service). It
adds a backend module (`app/{models,schemas,services,api/v1}/restaurant*`) and three
frontend surfaces:

| Surface | URL | Auth |
|---------|-----|------|
| Guest opt‑in (scan a table QR) | `/r/{venueSlug}/t/{tableToken}` | public |
| Staff scanner (scan & burn) | `/staff/redeem` | any signed‑in user |
| Owner console (stats, offers, tables, QR, campaigns) | `/restaurant/manage` | Manager+ |

WhatsApp reuses the existing WhatsApp Cloud API module (outbox worker + webhook).
Until a real number is connected, voucher/campaign delivery runs in **`simulated`**
mode so the whole flow is demoable.

---

## 1. Prerequisites
- Docker + docker‑compose on the host, TLS terminated at nginx (camera QR scanning
  and PWA install **require HTTPS**).
- A registered domain pointing at the host (this becomes `FRONTEND_URL`).
- For live WhatsApp: a **Meta Business** account with WhatsApp Cloud API — a
  Phone Number ID, WABA ID, a **permanent** access token, and the App Secret.

## 2. Environment (`.env`, from `.env.production.example`)
Set at minimum:
```
ENVIRONMENT=production
JWT_SECRET_KEY=<openssl rand -hex 32>
POSTGRES_SERVER/USER/PASSWORD/DB=...
REDIS_PASSWORD=...
BACKEND_CORS_ORIGINS=https://yourdomain.com
FRONTEND_URL=https://yourdomain.com        # NEW — builds QR scan URLs; no trailing slash
TELEPHONY_ENCRYPTION_KEY=<base64 32 bytes>  # NEW — encrypts WhatsApp creds at rest
```
Generate the encryption key once:
```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
```
> `FRONTEND_URL` **must** be correct — table QR codes encode `FRONTEND_URL/r/{slug}/t/{token}`.
> `TELEPHONY_ENCRYPTION_KEY` **must** be stable — rotating it invalidates stored WhatsApp tokens.

## 3. Deploy (schema + app)
The compose stack runs migrations as a dedicated one‑shot `migrate` service before
the app starts (app runs as the unprivileged runtime role, no DDL):
```bash
docker compose -f docker-compose.prod.yml up -d --build
# migrate → alembic upgrade head → backend + web come up
```
The restaurant tables are created by migration **`restaurant_qr_0001`**, which also
merges the previously‑diverged Alembic heads, so `alembic upgrade head` is
unambiguous (verified: single head, 108 revisions, no cycles).

Verify:
```bash
docker exec crm-backend curl -fs localhost:8000/api/v1/health
```

## 4. Create the restaurant tenant
Each restaurant is a CRM **organization**. Onboard via the normal CRM signup
(`/register`) or provision directly. For a ready‑to‑show demo tenant:
```bash
docker exec crm-backend python seed_restaurant_demo.py   # prints logins + URLs
```
The owner (OrgAdmin/Manager) then opens **`/restaurant/manage`** to:
1. Create/confirm the **venue** and its **offer(s)**.
2. Add **tables** (single or bulk) and **Print all QR** → print/laminate the stands.
3. Place a stand on each table.

## 5. Connect WhatsApp Cloud API (go live — flips `simulated` → real)
1. In Meta App Dashboard, add the **WhatsApp** product; note **Phone Number ID**,
   **WABA ID**, generate a **permanent access token**, and copy the **App Secret**.
2. Link the number to the venue (credentials are encrypted at rest):
   ```bash
   docker exec -e TELEPHONY_ENCRYPTION_KEY=$TELEPHONY_ENCRYPTION_KEY crm-backend \
     python connect_whatsapp.py \
       --venue-slug <venue-slug> \
       --phone-number-id <id> --business-account-id <waba> \
       --access-token "<permanent token>" \
       --verify-token "<choose-any-string>" \
       --app-secret "<meta app secret>" \
       --sender-number "+91XXXXXXXXXX"
   ```
3. In Meta App Dashboard → **WhatsApp → Configuration → Webhook**:
   - **Callback URL:** `https://yourdomain.com/api/v1/whatsapp/webhook`
   - **Verify Token:** the exact `--verify-token` you used
   - **Subscribe to:** the `messages` field
4. Approve a **marketing template** in Meta for out‑of‑24h‑window campaigns
   (the campaign body auto‑appends the required "Reply STOP to opt out" line).

After this, vouchers and campaigns send for real (campaign result `channel: whatsapp`),
and inbound **STOP/START** replies auto opt‑out/opt‑in the guest (handled in the
existing webhook → `RestaurantService.apply_inbound_optout`).

## 6. Go‑live checklist
- [ ] `FRONTEND_URL` + `TELEPHONY_ENCRYPTION_KEY` set; stack up; `/api/v1/health` OK.
- [ ] Owner can log in and see `/restaurant/manage`.
- [ ] Venue + at least one active offer + tables created; QR stands printed.
- [ ] Scan a table QR on a phone → opt‑in issues a voucher.
- [ ] `connect_whatsapp.py` run; Meta webhook **Verified** (green) and `messages` subscribed.
- [ ] Test send: opt‑in with your own number → voucher arrives on WhatsApp.
- [ ] Staff can `/staff/redeem`, look up + burn; second burn is refused.
- [ ] Reply **STOP** from the test number → guest shows **Opted out**; campaign preview drops them.

## 7. Troubleshooting
- **QR opens a broken/relative URL** → `FRONTEND_URL` unset or wrong. Fix env, redeploy.
- **Delivery shows `simulated`** → no WhatsAppSettings linked to the venue; run `connect_whatsapp.py`.
- **Webhook won't verify** → verify token mismatch, or callback URL not HTTPS‑reachable.
- **`TELEPHONY_ENCRYPTION_KEY must be set`** → add it to the backend env (and keep it stable).
- **Camera scan unavailable** → not HTTPS, or iOS Safari (no `BarcodeDetector`); manual code entry always works.
- **Multi‑tenant WhatsApp:** give each paying restaurant its **own** WABA/number
  (shared numbers risk platform‑wide quality/ban if one triggers spam complaints).
