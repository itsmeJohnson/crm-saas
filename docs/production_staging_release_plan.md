# Production Staging & Release-Readiness Plan

**Mode:** READ-ONLY audit + plan. No code/migration/config/DB/branch changes; nothing pushed, merged, or deployed.
**Date:** 2026-08-20
**Release candidate:** `feat/phase4-config-engine @ cc146e0` (local only)
**Production:** `7382aee` @ VPS · merge-base `e8635db`

---

## 1. Executive summary

`cc146e0` is a **forward superset of production** (production functionality + Phase 3.1 guards + Phase 4.1 Custom Fields + Phase 4.2 Custom Objects). Branch-integrity verification confirms every production feature area is present as code and tests. The three pending migrations form a **single linear head** (`c1d2e3f4a5b6`) that applies **cleanly and non-destructively** against production's verified schema and against real PostgreSQL 18.3. The **only** hard configuration change required is disabling `RUN_CREATE_ALL` (production currently `true`; the release code fails closed on that). Release is **not** "deploy now" — it is gated on a **staging restore-and-verify pass** using a production backup. **Overall: 🟡 YELLOW** — no red blockers, but staging evidence does not yet exist.

## 2. Current production state (verified read-only earlier)

| Item | Value |
|---|---|
| Git HEAD | `7382aee` (dental product line) |
| Alembic current / head | `treatment_catalog_0001` |
| `custom_object_definitions` / `_records` | absent |
| `product_catalog_items` | absent; `treatment_catalog_items` present |
| `organizations` industry columns | absent |
| `RUN_CREATE_ALL` / `ENVIRONMENT` | `true` / `production` |
| Config guard on box | none (prod code predates it) |

## 3. Current release-branch state

`cc146e0` = 50/51 prod commits patch-equivalent + the 51st's artifacts present + Phases 3.1/4.1/4.2 + migrations `b9e387d2eb8e → 7b9a4002721f → c1d2e3f4a5b6`. Local FE `vitest 261` / `tsc` / `build` pass; BE new suites green; PostgreSQL 18.3 migration + services + query engine verified.

## 4. Corrected reconciliation findings

The earlier "divergent branches / 51 commits lost" conclusion was **wrong** (hash-based + path typos). Patch-equivalence (`git cherry -v cc146e0 7382aee`) = **50 `-`, 1 `+`**; the `+` commit's functional artifacts all exist in `cc146e0`. **`cc146e0` is production, rebased, plus the config engine.** See `docs/production_reconciliation_plan.md`.

## 5. Production functionality inventory (branch-integrity, verified in `cc146e0`)

| Area | Artifact(s) in `cc146e0` | Status |
|---|---|---|
| Dental pages | `frontend/src/pages/dental/*` | ✅ present |
| Dental mobile (Android) | `mobile/android/**/feature/dental/*` | ✅ present |
| **Odontogram** | *none in either branch* | ⚪ **not a gap** — never implemented in prod either (commit-message only) |
| Invoice PDF | `services/customer_invoice_pdf.py`, `components/dental/CreateInvoiceModal.tsx` | ✅ present |
| Treatment catalog | `services/treatment_catalog_service.py` (compat) + `product_catalog_service.py` | ✅ present (renamed w/ alias) |
| WhatsApp Business | `services/whatsapp_service.py`, `test_whatsapp_module.py` | ✅ present |
| Trials / provisioning | `services/trial_provisioning.py`, `test_trial_requests.py` | ✅ present |
| Lead capture | `api/v1/lead_capture.py` | ✅ present |
| Auth / super-admin | `api/v1/super_admin.py`, `test_super_admin.py`, `test_lead_security_matrix.py` | ✅ present |
| Custom Fields / Objects | `custom_field_service.py`, `custom_object_service.py`, `test_custom_fields.py`, `test_custom_objects.py` | ✅ present |
| Test suite | `backend/app/tests/` | ✅ **139 test files** |

**Branch integrity: PASS** — no production feature is missing from the release candidate.

## 6. Migration analysis

- **Chain (linear, single head):** `… → treatment_catalog_0001 → b9e387d2eb8e → 7b9a4002721f → c1d2e3f4a5b6`.
- **No prod-only migration files;** config-only = the 3 new ones. Shared migrations carry **identical `down_revision`s** on both branches (`metadata_engine_0001`→`b2c9befa8805`, `treatment_catalog_0001`→`org_invoice_settings_0001`, `org_invoice_settings_0001`→`lead_capture_0001`) → no duplicate-id / divergent-thread fork.
- **Pending vs prod DB (all non-destructive, guarded):**
  | Migration | Op | Prod pre-state | Verdict |
  |---|---|---|---|
  | `b9e387d2eb8e` | add org industry cols | absent | ✅ clean |
  | `7b9a4002721f` | rename treatment→product (inspector-guarded) | treatment present / product absent | ✅ clean |
  | `c1d2e3f4a5b6` | create custom_object tables (guarded) | absent | ✅ clean |
- **`create_all` conflict risk:** none for the pending set — `product_catalog_items` and `custom_object_*` don't yet exist in prod, so nothing collides. (General `create_all` risk is retired once `RUN_CREATE_ALL=false`.)
- **Caveat:** the full DAG is large and history contains prior `merge_heads` revisions → confirm `alembic heads` = single head on a **clean staging checkout**.

## 7. Configuration analysis — required changes (documented, not applied)

| Setting | Current prod | Required for release | Why |
|---|---|---|---|
| `RUN_CREATE_ALL` | `true` | **`false` / unset** | Release `config.py` raises at `Settings()` if truthy in production → backend won't boot |
| `ENVIRONMENT` | `production` | unchanged | correct |
| Schema authority | create_all | **Alembic (`upgrade head`)** | tables now come from migrations |
| `DATABASE_URL` / `MIGRATOR_DATABASE_URL` | POSTGRES_* single-role (untracked compose) | unchanged (optional WP-03A role split) | migrate step uses `migrator_database_uri` |
| Compose / migrate service | **unconfirmed** (dev `compose.yml` vs `docker-compose.prod.yml`) | confirm which is live | determines whether `migrate` service or in-container fallback runs alembic |
| Backup / rollback | `ops/backup.sh` (daily + pre-deploy), git checkout | unchanged | already sound |

## 8. Staging deployment sequence (design only — DO NOT EXECUTE)

1. Fresh prod backup (`ops/backup.sh`), verify integrity.
2. Restore backup → **staging** Postgres (`ops/restore.sh <dump>` into a staging DB).
3. Deploy `cc146e0` to staging (build).
4. Set `RUN_CREATE_ALL=false` (unset) in staging env.
5. `alembic upgrade head` (dedicated migrate step) in staging.
6. Verify: `alembic current == c1d2e3f4a5b6`; single head; `\dt custom_object*` present; `product_catalog_items` present.
7. Verify existing data survived (row counts vs pre-migration snapshot).
8–12. Execute the §9 regression matrix (core, dental, billing, WhatsApp, trials/lead-capture, custom fields/objects, tenant isolation).
13. Backend tests (`pytest`).
14. Frontend tests (`vitest`).
15. `tsc --noEmit`.
16. Production frontend build.
17. Health endpoint (httpx probe, not curl).
18. Review startup + migration logs for errors.
19. Compare key record counts before/after.
20. Produce release certification.

## 9. Production regression matrix (staging)

| # | Domain | Test | Expected | Type | Sev |
|---|---|---|---|---|---|
| A | Core CRM | auth login/OTP; tenants; users/RBAC; leads/contacts/customers/opps/pipeline/activities CRUD; search; imports | pass | auto+manual | P0 |
| B | Dental | module gating on; treatment catalog list/CRUD (via compat over `product_catalog_items`); dental pages render; dental permissions; dental data isolation | pass | manual+auto (`test_treatment_catalog`, `test_industry_scoping`) | P0 |
| C | Billing | invoice CRUD; PDF generation; invoice customization; billing pages; **billing search**; plan/pricing | pass | manual+auto (`test_invoice_settings`, `test_invoice_config`) | P0 |
| D | WhatsApp | config; webhook handling; message ops; tenant isolation | pass | auto (`test_whatsapp_module`) + manual | P1 |
| E | Trials / lead capture | signup; provisioning; welcome flow; inbound capture; lead creation | pass | auto (`test_trial_requests`) + manual | P1 |
| F | Custom Fields | 13 types; Lead+Contact fields; validation; reserved keys; tenant isolation; legacy fields | pass | auto (`test_custom_fields`, `test_phase2_services`) | P1 |
| G | Custom Objects | object def; fields; records CRUD; filter/sort/paginate; entity_reference (single+multi); cross-tenant; delete protection | pass | auto (`test_custom_objects`) | P1 |
| H | Architecture | Core industry-independent; dental module-gated; no Core→Dental import; tenant/module boundaries | pass | auto (`test_architecture_boundary`) | P0 |
| — | DB | single alembic head; row counts unchanged; backup+restore | pass | manual | P0 |
| — | Ops | deploy; rollback; health | pass | manual | P0 |

## 10. Data-integrity checks

- Snapshot **before** upgrade: `SELECT relname, n_live_tup FROM pg_stat_user_tables` (or per-table counts for organizations, users, leads, contacts, invoices, treatment/product catalog, custom_field_definitions).
- After upgrade: identical counts for all pre-existing tables; `treatment_catalog_items` **renamed** to `product_catalog_items` with the same row count; new `custom_object_*` empty.
- Zero rows lost; no truncation; no unexpected nulls in migrated columns.

## 11. Rollback plan

- **Preferred:** code rollback + restore. `git checkout 7382aee && docker compose up -d --build backend frontend`, restore the pre-deploy backup if any data changed. Tag `7382aee` (e.g. `pre-phase4`) before deploy.
- **Migration-level (staging only, avoid on live data):** each pending migration has a guarded `downgrade` (custom_object tables dropped; product→treatment renamed back; industry cols dropped). Only the treatment↔product rename is data-shaped; its downgrade renames back.

## 12. Release gates (objective PASS/FAIL)

| Gate | PASS criterion |
|---|---|
| 1 — Branch integrity | All critical prod features present in `cc146e0` — **PASS (verified §5)** |
| 2 — Migration integrity | Staging upgrades cleanly to `c1d2e3f4a5b6`, single head — *pending staging* |
| 3 — Data integrity | Pre-existing rows survive; counts match; catalog rename preserves rows — *pending staging* |
| 4 — Dental regression | Dental workflows + catalog function via compat — *pending staging* |
| 5 — Billing regression | Invoices/PDF/search/pricing function — *pending staging* |
| 6 — WhatsApp regression | Config/webhook/messaging function — *pending staging* |
| 7 — Tenant isolation | Cross-tenant access blocked (all domains) — *pending staging* |
| 8 — Custom Fields | All Phase 4.1 tests pass — **PASS locally**, re-run on staging |
| 9 — Custom Objects | All Phase 4.2 tests pass — **PASS locally**, re-run on staging |
| 10 — Prod config | `RUN_CREATE_ALL` disabled; Alembic is schema authority — *config change pending* |
| 11 — Automated verification | pytest/vitest/tsc/build acceptable; all failures understood (date/redis flakes) — **PASS locally**, re-run on staging |

**Release approved only when Gates 1–11 are all PASS on staging.**

## 13. Known risks

1. `git cherry` patch-id can misjudge reworked/squashed commits → the §9 dental/billing regression suite is the **authoritative** proof, not the git analysis.
2. Live VPS's **active compose file unconfirmed** (dev `compose.yml` vs `docker-compose.prod.yml`) → affects how alembic runs; confirm before deploy.
3. Large alembic DAG + historical `merge_heads` → confirm single head on clean checkout.
4. `RUN_CREATE_ALL` must be flipped **before** the new code starts, or the backend won't boot.
5. Treatment→product rename is the one data-shape change — staging must prove dental billing/catalog still resolve through the compat layer.

## 14. Required human approvals

- Approve `feat/phase4-config-engine` as the canonical release line.
- Approve the `RUN_CREATE_ALL=false` production env change.
- Approve restoring a prod backup copy into staging.
- Sign off staging Gates 2–7, 10 before prod.

## 15. Exact commands to execute during staging (reference — run on staging infra, not here)

```bash
# 0) fresh backup on prod
cd /opt/apps/crm && ./ops/backup.sh

# 1) restore into a STAGING database (never over live)
ops/restore.sh /opt/backups/crm/crm-<latest>.sql.gz     # restores into crm_restore by default

# 2) pre-migration row snapshot (staging DB)
docker exec postgres psql -U johnson -d crm_restore -c \
  "SELECT relname,n_live_tup FROM pg_stat_user_tables ORDER BY relname;"

# 3) deploy cc146e0 to STAGING + set the flag off (staging env), then migrate
#    (RUN_CREATE_ALL unset/false in the staging env before the backend starts)
docker compose run --rm migrate            # or: docker exec <staging-backend> alembic upgrade head

# 4) verify migration state
docker exec <staging-backend> alembic heads      # expect single head c1d2e3f4a5b6
docker exec <staging-backend> alembic current    # expect c1d2e3f4a5b6
docker exec postgres psql -U johnson -d crm_restore -c "\dt custom_object*"
docker exec postgres psql -U johnson -d crm_restore -c "\dt *catalog*"   # product_catalog_items present

# 5) post-migration row snapshot + diff vs step 2
docker exec postgres psql -U johnson -d crm_restore -c \
  "SELECT relname,n_live_tup FROM pg_stat_user_tables ORDER BY relname;"

# 6) automated suites (staging backend/frontend)
docker exec <staging-backend> python3 -m pytest -q
#   frontend: npx vitest run ; npx tsc --noEmit ; npm run build

# 7) health
docker exec <staging-backend> python -c "import httpx;print(httpx.get('http://localhost:8000/api/v1/health').status_code)"
```

## 16. Exact evidence required for production approval

- `alembic current == c1d2e3f4a5b6`; `alembic heads` single-head (staging).
- `\dt` showing `custom_object_definitions`, `custom_object_records`, `product_catalog_items` present; `treatment_catalog_items` gone.
- Row-count diff (steps 2 vs 5) showing **no loss**; catalog rename preserves count.
- Green regression matrix (§9) — especially dental, billing, WhatsApp, tenant isolation (P0/P1).
- pytest/vitest/tsc/build results with any failures explained (known redis/date flakes only).
- Backend startup + migration logs clean.
- Confirmed `RUN_CREATE_ALL=false` in the target environment.

---

## Final status

- **Verified now (read-only):** branch integrity (Gate 1 PASS — all prod features present in `cc146e0`, 139 tests; odontogram absent in *both*, not a gap); migration lineage (linear, single head, non-destructive, clean vs prod DB); PostgreSQL correctness (done earlier); config delta (`RUN_CREATE_ALL` must flip).
- **Remains unverified (needs staging):** Gates 2–7 and 10 — real migration apply on a prod-data copy, data integrity, and dental/billing/WhatsApp/tenant-isolation regression under production data.
- **Staging prerequisites:** a staging Postgres, a fresh prod backup, a staging deploy of `cc146e0` with `RUN_CREATE_ALL=false`, and access to run the §9 matrix.
- **Release blockers:** (1) staging regression pass not yet run; (2) `RUN_CREATE_ALL=false` env change; (3) confirm live compose + single head.
- **Exact next action:** on staging infra — **restore a prod backup, deploy `cc146e0` with `RUN_CREATE_ALL=false`, run `alembic upgrade head`, then execute the §9 regression matrix and capture §16 evidence.** (Not runnable from this session — needs your staging/VPS access.)
- **Release readiness: 🟡 YELLOW** — no red blockers; branch + migration + local/PostgreSQL evidence are green; production approval is gated solely on the staging regression pass and the config flag.

*Audit + plan only. No implementation, migration, config, DB, commit, push, PR, merge, or deploy performed. Phase 4.3 not started.*
