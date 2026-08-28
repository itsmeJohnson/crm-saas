# Production ↔ Config-Engine Reconciliation Plan

**Mode:** read-only analysis. No source/DB/env/migration/branch changes were made.
**Date:** 2026-08-20
**Branches:** production `7382aee` · config-engine `feat/phase4-config-engine @ cc146e0` · merge-base `e8635db`

---

## ⚠️ Correction to the prior audit (important)

An earlier message concluded the branches were *divergent product lines* and that deploying `cc146e0` would **lose 51 commits of production functionality**. **That conclusion was wrong.** It was based on commit-**hash** divergence plus two mistaken `ls` path checks. The correct tool — **patch-equivalence (`git cherry`)** — shows the opposite:

- **50 of 51** production commits are **already present** in config-engine (re-committed with new hashes via rebase/PR merges).
- The **1** remaining (`df908575` trial-registration/email-normalization) has **all its functional artifacts present** in config-engine (`email_utils.py`, `trial_request.py`, `email_normalize_0001`, `b2c9befa8805`); its `+` mark is a patch-id artifact (it also bundled binary docs).
- Dental / mobile / android code **is present** (`mobile/android/*`, `frontend/src/{pages,components}/dental/*` all exist in `cc146e0`).

**Corrected model: config-engine ≈ production + Phases 3.1/4.1/4.2.** It is a **forward superset**, not a competing fork. This makes reconciliation *tractable* — largely **verification**, not a hazardous merge.

---

## 1. Executive summary

`feat/phase4-config-engine` already contains essentially all production functionality plus the Configuration Engine (Custom Fields 4.1, Custom Objects 4.2, arch guards 3.1) and three new migrations. Deploying it is a **forward release**, gated on: (a) flipping `RUN_CREATE_ALL=false` in prod env (else the hardened backend refuses to boot), (b) applying 3 pending migrations (verified clean against prod's live schema), and (c) a **staging feature-regression pass** to confirm the genericization (treatment→product rename, metadata-engine extension) preserved dental/billing/WhatsApp/mobile behavior. **RELEASE READY: NO** until staging passes; **MIGRATION READY: YES** (pending the flag); **STAGING REQUIRED: YES.**

## 2. Git topology

```
        e8635db  (merge-base: "docs: project status & architecture")
           │
   ┌───────┴───────────────────────────────┐
   │ (production line, 51 commits)          │ (config-engine line, 65 commits)
   ▼                                        ▼
 7382aee  PRODUCTION                     cc146e0  feat/phase4-config-engine
 dental product @ live VPS              = 50/51 prod commits (re-hashed)
                                          + Phase 3.1 / 4.1 / 4.2
                                          + migrations b9e387d2eb8e, 7b9a4002721f, c1d2e3f4a5b6
```

`git cherry -v cc146e0 7382aee` → **50× `-` (present), 1× `+` (artifact)**. Neither tip is a strict ancestor; config-engine is the functional superset.

## 3. Commit classification (summary)

| Group | Count | Classification | Notes |
|---|---|---|---|
| Prod commits patch-present in config | 50 | **B — already superseded/present** | dental, invoices, plans, trials, WhatsApp, lead-capture, ops, auth |
| Prod commit flagged `+` (`df908575`) | 1 | **F — verify** | artifacts present; confirm via targeted diff, not assumed missing |
| Config-only work (Phases 3.1/4.1/4.2, WP-03A role sep, CI fixes) | 65 | **A — must preserve** | the new capability being shipped |

## 4. File conflict map

From merge-base `e8635db`: prod changed **234** files, config changed **326**, with **231 changed by both**. Because config-engine was built *on* the prod line, "both-modified" here means **config-engine carries prod's change and then extends it** — not a symmetric conflict. Representative both-touched areas and how config relates:

| Area | Files | Config-engine relationship |
|---|---|---|
| Metadata/custom-fields | `custom_field_definition.py`, `custom_field_service.py` (+56 lines), `metadata_validation_engine.py` (+387 lines), `metadata_cache_service.py` | **Extends** prod's engine (Phase 4.1) — superset, not conflict |
| Catalog | `treatment_catalog*.py`, `product_catalog*` (new) | Phase 3 **rename + compat alias** (`TreatmentCatalogService(ProductCatalogService)`) |
| Core | `config.py`, `main.py`, `organization.py`, `lead.py`, `pipeline.py` | config adds Phase 1–4 columns/guards on top of prod |
| Dental FE/mobile | `frontend/src/{pages,components}/dental/*`, `mobile/android/*` | present in config (carried from prod) |
| Ops | `ops/*.sh`, `docker-compose*.yml` | present in config (re-hashed prod ops commits) |

**A true 3-way merge is *not* required** for a forward deploy of config-engine (it already contains prod). A merge would only be needed if prod acquires *new* commits after `7382aee` before release.

## 5. Dental / clinical preservation matrix

| Feature | Prod impl | Config-engine | Action |
|---|---|---|---|
| Dental module + gating | `require_module`, dental pages, `industries.py` | Present + gated (Phase 3.1) | **ALREADY PRESENT** |
| Treatment catalog | `treatment_catalog_items` / `TreatmentCatalogService` | Renamed→`product_catalog_items` with `TreatmentCatalog*` **compat alias** + migration `7b9a` | **RECONCILE via compat (already built)** — verify on staging |
| Odontogram / patient / appointments UI | dental components | Present in `cc146e0` | ALREADY PRESENT |
| Invoice PDF + WhatsApp share | `customer_invoice_pdf.py`, public link | Present | ALREADY PRESENT |
| Android/mobile dental app | `mobile/android/**` | Present (both-modified) | **MANUAL REVIEW** — confirm API contract unchanged by Phase 3 rename |
| Clinical RBAC | permissions | Present | ALREADY PRESENT |

**No feature is slated to drop.** The one behavior that *changes* is the catalog table/name (treatment→product), mitigated by the compat layer Phase 3.1 verified.

## 6. Metadata / custom-fields reconciliation

They are **one system, evolved forward** — not two competing implementations. Config-engine's `custom_field_definition` / `metadata_validation_engine` / `metadata_cache_service` are prod's `metadata_engine_0001` foundation **extended** by Phase 4.1 (13 types, reserved keys, entity allowlist) and 4.2 (object entity types). Migration `metadata_engine_0001` has an **identical `down_revision` (`b2c9befa8805`) on both branches** → no lineage fork. Canonical = config-engine (superset). Prod data in `custom_field_definitions` remains valid (config only *adds* capability; existing rows/keys keep working — verified by the Phase 4.1 backward-compat tests).

## 7. Alembic lineage reconciliation

- **Prod-only migration files: NONE.** Config-only: exactly the 3 new ones (`b9e387d2eb8e`, `7b9a4002721f`, `c1d2e3f4a5b6`).
- Shared migrations carry **identical `down_revision`s** on both branches (spot-checked `metadata_engine_0001`, `treatment_catalog_0001`, `org_invoice_settings_0001`).
- Config-engine chain is **single-headed**: `… treatment_catalog_0001 → b9e387d2eb8e → 7b9a4002721f → c1d2e3f4a5b6`.
- Prod is stamped at `treatment_catalog_0001` (an ancestor of the config head).
- **Result: ONE linear head (`c1d2e3f4a5b6`) is achievable with no divergent-head merge and no destructive ops.** (Note: the repo history shows prior `merge_heads` revisions — confirm on staging that `alembic heads` resolves to a single head after checkout, since the DAG is large.)

## 8. Database compatibility (vs verified prod state)

Prod: `alembic_current=treatment_catalog_0001`, `treatment_catalog_items` present, `product_catalog_items`/`custom_object_*` absent, org industry cols absent, `RUN_CREATE_ALL=true`.

| Pending migration | Op | Prod pre-state | Verdict |
|---|---|---|---|
| `b9e387d2eb8e` | add org industry cols | cols absent | ✅ clean add |
| `7b9a4002721f` | rename treatment→product (inspector-guarded) | treatment present, product absent | ✅ clean rename |
| `c1d2e3f4a5b6` | create custom_object tables (guarded) | absent | ✅ clean create |

All three map to their expected pre-state on the live DB (also independently verified on real PostgreSQL 18.3). **No operation is destructive; no create_all-created object collides** (product_catalog_items and custom_object_* don't yet exist in prod).

## 9. RUN_CREATE_ALL transition

- Prod code (`7382aee`) has **no** production guard → runs with `RUN_CREATE_ALL=true` today.
- Config-engine `config.py` **raises in `Settings()` at startup** if `RUN_CREATE_ALL` is truthy in production (fail-closed) → backend won't boot on the new code until the flag is cleared.
- **Required final config:** unset/`false` `RUN_CREATE_ALL` in the prod env; schema comes from `alembic upgrade head`. The dedicated `migrate` step in `docker-compose.prod.yml` does not set the flag, so it is unaffected; if the live box still runs the untracked dev `compose.yml`, the flag must be removed there.

## 10. Deployment / ops reconciliation

Config-engine already contains the prod ops tooling (`ops/deploy.sh`, backup/restore, `docker-compose.prod.yml` migrate service) — re-hashed from prod. **Keep prod's ops mechanism** (it is the same). `deploy.sh` already does `backup → pull → build → alembic upgrade head → health`. One caveat: `deploy.sh` runs bare `docker compose` (resolves to whichever compose file the box uses) and references `crm-backend`; confirm the live box's active compose before relying on the `migrate` service vs the in-container fallback.

## 11. Staging verification matrix (required before prod)

| Domain | Test | Expected | Type | Blocker |
|---|---|---|---|---|
| Auth | login, OTP reset, tenant isolation | pass | auto+manual | P0 |
| Core CRM | leads/contacts/pipeline/opps/activities CRUD | pass | auto (pytest) | P0 |
| Billing | invoices, PDF, WhatsApp share link | pass | manual | P0 |
| Dental | module gating, treatments, **treatment→product catalog**, odontogram, dental dashboard, clinical RBAC | pass, catalog intact via compat | manual | P0 |
| Comms | WhatsApp Business send/template/webhook | pass | manual | P1 |
| Commercial | plans, promo pricing, trials, subscriptions | pass | manual | P1 |
| Customization | custom fields, custom objects, records, filter/sort, tenant isolation | pass (new) | auto (pytest) | P1 |
| Mobile | Android build + API contract post-rename | pass | manual | P1 |
| DB | single alembic head `c1d2e3f4a5b6`, row counts unchanged, backup+restore | pass | manual | P0 |
| Ops | deploy, rollback, health (httpx probe) | pass | manual | P0 |

**Method:** restore a prod backup into a staging DB, deploy `cc146e0` against it with `RUN_CREATE_ALL=false`, run `alembic upgrade head`, then execute the matrix. This is the real gate.

## 12. Recommended reconciliation strategy → **A (deploy config-engine as the release), guarded**

Given config-engine already contains prod (50/51 patch-equivalent + all artifacts of the 51st):

- **A (recommended): treat `feat/phase4-config-engine` as the release line** and deploy it forward, guarded by the §11 staging matrix. Lowest conflict count (config already integrates prod), fully reviewable, preserves dental via the compat layer.
- **Not B/C/D** (cherry-pick / rebase / new-branch-from-prod): unnecessary — config-engine is *already* the reconciled superset. Re-deriving it would add risk, not remove it.
- **Only if prod gains NEW commits after `7382aee` before release:** merge those specific new commits into `feat/phase4-config-engine` first (small, targeted), then proceed with A.

Evaluation: data-safety ✅ (non-destructive migrations), migration-safety ✅ (linear head, verified), dental preservation ✅ (present + compat + staging), conflict count **low**, rollback **simple** (git checkout `7382aee` + `docker compose up`), reviewability ✅ (PR diff), maintainability ✅ (single forward line).

## 13. Proposed branch topology

```
main
 └── feat/phase4-config-engine  (cc146e0)  ──►  rename to release/phase4-config-engine
        = production (7382aee, rebased)  +  Phase 3.1 / 4.1 / 4.2
        → PR → review → staging verify → tag vX.Y.0 → deploy
```
Rationale: config-engine is already the integrated line; formalize it as the release branch, PR for review, tag for rollback.

## 14. Theoretical migration sequence (documentation only — do NOT execute)

1. `ops/backup.sh` (fresh, verified restore).
2. Restore backup → **staging** DB; run steps 4–6 there first; execute §11 matrix.
3. In prod env: **unset `RUN_CREATE_ALL`** (set `false`).
4. Deploy `cc146e0` code (build).
5. `alembic upgrade head` via the dedicated migrate step → applies `b9e387d2eb8e`, `7b9a4002721f`, `c1d2e3f4a5b6`.
6. Verify: `alembic current == c1d2e3f4a5b6`, single head; `\dt custom_object*` present; `product_catalog_items` present (renamed); row counts unchanged.
7. Backend start → health (httpx probe).

## 15. Rollback strategy

`git checkout 7382aee && docker compose up -d --build backend frontend`. The 3 migrations are reversible (each has a guarded `downgrade`), but **prefer code rollback + restore from the pre-deploy backup** over `alembic downgrade` on live data. The treatment→product rename is the only data-shape change; its downgrade renames back. Tag `7382aee` before deploy for instant rollback.

## 16. Release blockers

1. **Staging feature-regression pass** (§11) — not yet run. **P0.**
2. **`RUN_CREATE_ALL=false` env transition** — else backend won't boot on new code. **P0.**
3. **Verify commit `df908575` effect** via targeted diff (artifacts present; confirm no behavior gap). **P1.**
4. **Confirm live box's active compose** (dev `compose.yml` vs `docker-compose.prod.yml`) so migrations run the intended way. **P1.**
5. **Single-head confirmation** on a clean checkout given the large DAG + historical merge_heads. **P1.**

## 17. Human approval decisions

- Approve treating `feat/phase4-config-engine` as the canonical release line.
- Approve the `RUN_CREATE_ALL` env change on production.
- Approve the staging-restore-and-verify plan (uses a prod backup copy).
- Sign off the dental/billing/WhatsApp/mobile regression results before prod.

---

## Final certification

- **RELEASE READY: NO** — pending the staging regression pass and the `RUN_CREATE_ALL` transition. (Not blocked by branch divergence — config-engine already contains production.)
- **MIGRATION READY: YES** — the 3 pending migrations are non-destructive, single-headed, and verified clean against prod's live schema and real PostgreSQL; contingent on `RUN_CREATE_ALL=false`.
- **STAGING REQUIRED: YES** — restore-prod-backup → deploy `cc146e0` → `alembic upgrade head` → run the §11 matrix.

**Residual uncertainty (explicit):** (a) `git cherry` patch-id can misjudge squashed/reworked commits — the §11 dental/billing regression suite is the authoritative check that nothing regressed; (b) the live VPS's active compose file is unconfirmed; (c) single-head resolution on the full DAG should be confirmed on a clean checkout.

*No implementation, merge, rebase, cherry-pick, migration, commit, push, or PR was performed. Analysis only.*
