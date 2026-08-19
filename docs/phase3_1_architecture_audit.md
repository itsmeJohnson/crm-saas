# Phase 3.1 — Generic CRM Core Architecture Audit

**Date:** 2026-08-19
**Branch:** `fix/security-test-feature-gate`
**Scope:** READ-ONLY audit of the CRM Core to certify it can operate independently of the Dental industry module, followed by the minimum safe enforcement changes.

**Certification question:** *Can the CRM Core operate independently of Dental?*
**Answer:** **Yes.** Proven below by code dependency analysis and by the tenant-scoping + architecture-guard test suites. No Core model, repository, service, schema, store, or domain component has a hard dependency on any Dental entity. Dental is gated as an industry module and can be fully disabled per tenant.

---

## 1. Core Entities vs Industry Entities

### Core entities (industry-neutral)

| Entity | Model | Table | Verdict |
|---|---|---|---|
| Lead | `models/lead.py` | `leads` | Generic ✅ |
| Contact | `models/contact.py` | `contacts` | Generic ✅ |
| Company | `models/company.py` | `companies` | Generic ✅ |
| Customer | `models/customer_*.py` | `customer_*` | Generic ✅ |
| Activity | `models/activity.py` | `activities` | Generic ✅ |
| Task | `models/task.py` | `tasks` | Generic ✅ |
| FollowUp | follow-up orchestration | — | Generic ✅ |
| Note | `models/note.py` | `notes` | Generic ✅ |
| Communication | `models/communication.py` | `communications` | Generic ✅ |
| Pipeline / PipelineStage | `models/pipeline.py` | `pipelines`, `pipeline_stages` | Generic ✅ |
| Opportunity | *(not a distinct table)* | — | Modeled as **Lead × Pipeline stage** ✅ |
| Tag | JSON column (`tags`) | — | Attribute, not entity ✅ |
| Attachment | JSON column (`attachments`) | — | Attribute, not entity ✅ |
| ProductCatalogItem | `models/product_catalog.py` | `product_catalog_items` | Generic ✅ |

> **Opportunity / Tag / Attachment are not first-class tables.** An Opportunity is a Lead progressing through configurable `PipelineStage`s (`is_won`/`is_lost`/`probability`). Tags and Attachments are JSON attributes on the core entities. This is a valid generic design — noted so the model is not mistaken for missing.

### Industry (Dental) entities

Dental has **no dedicated tables of its own.** All dental data is carried in the generic `custom_fields` JSON columns on core entities (Contact = "patient", etc.), plus one industry catalog:

| Dental module | Backing store | Nature |
|---|---|---|
| patients | `contacts` + `custom_fields` | Core entity, dental label |
| appointments | `calendar_events` (`event_type="Appointment"`) | Core entity, dental value |
| treatments / treatment_plans | `custom_fields` + `product_catalog_items` | Core + catalog |
| recall | follow-up engine | Core engine |
| dentists | `users` | Core entity, dental label |
| clinical_reports | reporting engine | Core engine |
| treatment-catalog (API) | `product_catalog_items` | **Compatibility wrapper** over ProductCatalog |

**Consequence:** disabling Dental removes *no* schema and orphans *no* data. Dental is a labeling + module-gating overlay on the generic core.

---

## 2. Dependency Graph

```
        ┌──────────────────────────────────────────────┐
        │                 CRM CORE                      │
        │  Lead · Contact · Company · Customer          │
        │  Activity · Task · Note · Communication       │
        │  Pipeline/Stage · ProductCatalogItem          │
        │  (all generic tables; dental data → custom_fields) │
        └──────────────────────────────────────────────┘
              ▲                    ▲                 ▲
              │ depends on         │ gated by        │ wraps
              │                    │                 │
   ┌──────────┴─────┐   ┌──────────┴──────────┐  ┌───┴─────────────────┐
   │ Dental module  │   │ require_module()    │  │ TreatmentCatalog*   │
   │ (patients,     │   │  ← industries.py    │  │  extends            │
   │  appointments, │   │    BUSINESS_TEMPLATES│  │  ProductCatalog*    │
   │  treatments…)  │   │  ← tenant_config     │  │ (compat alias)      │
   └────────────────┘   └─────────────────────┘  └─────────────────────┘

   Arrows point Industry → Core. No arrow points Core → Dental.  ✅
```

### Layer-by-layer trace (Lead as representative)

| Layer | File | Dental dependency? |
|---|---|---|
| Model | `models/lead.py` | **None** — grep for `patient_id/dentist_id/treatment_id/appointment_id` returns 0 hits across all `models/` |
| Repository | `repositories/lead_repository.py` | None |
| Service | `services/lead_service.py` | None |
| Schema | `schemas/lead.py` | None |
| Router | `api/v1/leads.py` | None |
| Store | `store/leadStore.ts` | None |
| Components | `components/leads/*` | None |
| Tests | `tests/…` | Test-only string mentions |

---

## 3. Dependency Classification (every dental-term hit)

Grep across `backend/app` and `frontend/src` for `patient|treatment|appointment|dentist|clinical|recall|tooth|procedure`, classified:

| Location | Hit | Class | Action |
|---|---|---|---|
| `models/*` columns | **0 dental columns** | — | None needed |
| `models/calendar_event.py` | `event_type` value `"Appointment"` | **A** config value | Keep |
| `models/product_catalog.py` | comment `SKU / procedure code` | comment | Keep |
| `schemas/customer.py`, `schemas/contact.py`, `schemas/calendar.py` | comments referencing patients/appointments | comment | Keep |
| `services/customer_service.py` | `_invoice_patient_and_consultant()` → delegates to `_invoice_contact_and_consultant()` | **C** legacy alias | Keep |
| `services/treatment_catalog_service.py` | `TreatmentCatalogService(ProductCatalogService)` | **C** compat | Keep |
| `services/lead_capture_service.py` | inbound alias `"treatment" → "title"` | **E** field mapping | Keep |
| `services/copilot_service.py`, `comm_intelligence_service.py` | NL regex includes `appointment` | **A** generic NLP | Keep |
| `core/industries.py` | Dental module names in `ALL_MODULES` / `BUSINESS_TEMPLATES` | **E** registry | Keep (correct place) |
| `schemas/treatment_catalog.py`, `api/v1/treatment_catalog.py` | Dental-named DTO/router, `require_module("treatments")` gated | **C** compat | Keep |
| `services/tenant_config_service.py` | **defaults null industry/template → `HEALTHCARE_DENTAL`** | **B** hidden default | **Recommend fix (deferred — migration risk)** |
| `store/metadataStore.ts` | offline fallback `enabled_modules` = full dental set | **B** hidden default | **Recommend fix (deferred)** |
| `routes/moduleRegistry.ts` | lazy-imports dental pages; core `billing`/`reports` route to `pages/dental/*` | **B** view-layer coupling | **Recommend fix (deferred — UI, out of Phase 3.1 scope)** |
| `layouts/AppLayout.tsx` | per-industry relabel map (dental → RE/Insurance/Loan terms) | **E** i18n overlay | Keep (this is the mitigation) |

Legend: **A** correct dental dep · **B** incorrect Core→Dental · **C** compat/legacy · **D** test-only · **E** config/template.

---

## 4. Violations Found

Only **three** Core→Dental couplings exist, all in the **default/label layer**, none in the domain/data layer:

- **V1 — Backend default bias (Class B).** `tenant_config_service.py` resolves a null `industry`/`business_template` to `HEALTHCARE_DENTAL`, so an unconfigured tenant silently receives dental modules. A generic core should default to `GENERIC`.
- **V2 — Frontend default bias (Class B).** `metadataStore.ts` offline fallback hard-codes the full dental module list.
- **V3 — View-layer coupling (Class B).** `moduleRegistry.ts` wires core `billing` (`/billing`) and core `reports` (`/marketing`) to `pages/dental/BillingPage` and `pages/dental/MarketingPage`. A non-dental tenant enabling billing renders the dental billing screen. Mitigated at runtime by `AppLayout.tsx` relabeling, but the component identity is still dental.

**No violation** exists in models, repositories, services (domain logic), schemas, routers, or core stores/components. The import direction **Industry → Core** holds throughout the domain layer.

---

## 5. Legacy / Compatibility Paths (intentional, keep)

- `TreatmentCatalogService(ProductCatalogService)` + `schemas/treatment_catalog.py` + `api/v1/treatment_catalog.py` — dental-named surface over the generic `product_catalog_items` table; gated by `require_module("treatments")`.
- `models/treatment_catalog.py`: `TreatmentCatalogItem = ProductCatalogItem` alias.
- `customer_service._invoice_patient_and_consultant()` → `_invoice_contact_and_consultant()`.
- Migration `7b9a4002721f_generify_product_catalog.py` renames `treatment_catalog_items → product_catalog_items` idempotently (guarded by table inspection; safe on SQLite **and** Postgres, and safe on a fresh prod DB with no prior table).

---

## 6. Recommended Fixes

| # | Fix | Enforced now? | Why / risk |
|---|---|---|---|
| R1 | Add **architecture-guard tests** asserting no Core model/service/store/component imports Dental, and that core models carry no dental FK columns | **✅ implemented this phase** | Zero runtime risk; locks the boundary going forward |
| R2 | Extend tenant matrix with explicit **403 on direct API** access to `treatment-catalog` for Insurance & Loan tenants | **✅ implemented this phase** | Completes item 10 proof |
| R3 | Default null industry/template to `GENERIC` (V1/V2) | ❌ **deferred** | **Migration risk:** existing prod dental tenants may have null `industry` and rely on the dental fallback. Flipping it would hide their dental modules. Requires a data backfill (`UPDATE organizations SET industry='healthcare_dental' WHERE industry IS NULL`) first. |
| R4 | Point core `billing`/`reports` routes at generic pages; move dental screens behind dental module keys (V3) | ❌ **deferred** | UI redesign — explicitly out of Phase 3.1 scope. |

---

## 7. Migration Risks

- **None introduced this phase.** The enforcement changes are test-only + no schema changes.
- **R3 (deferred)** carries the only real risk: changing the dental default without first backfilling `organizations.industry` for legacy null rows would drop dental tenants' modules. Prod currently has no alembic run and existing dental orgs — do **not** flip the default before the backfill.
- The Phase 3 catalog rename migration is idempotent and reversible.

---

## 8. Final Architecture Diagram

```
 Tenant (organization.industry / business_template / enabled_modules)
        │
        ▼
 TenantConfigurationResolver ──uses──► BUSINESS_TEMPLATES (core/industries.py)
        │  resolves enabled_modules
        ▼
 require_module(<key>)  ── 403 if key ∉ enabled_modules ──►  API routers
        │
        ├── CORE keys: dashboard, leads, contacts, companies, customers,
        │              activities, tasks, follow_ups, opportunities,
        │              pipelines, communications, billing, reports
        │                     │
        │                     ▼
        │              GENERIC DOMAIN  (Lead, Contact, Company, Customer,
        │              Activity, Task, Note, Communication, Pipeline,
        │              ProductCatalogItem)  ← industry data in custom_fields
        │
        └── DENTAL keys: patients, appointments, treatments, treatment_plans,
                         recall, dentists, clinical_reports
                              │
                              ▼
                    Dental UI pages + TreatmentCatalog compat wrapper
                              │
                              └── all read/write the SAME generic core tables

 Real Estate / Insurance / Loan tenants: dental keys absent → dental routes 403,
 dental pages never mounted, core domain fully operational.
```

**Certification:** The CRM Core is industry-neutral at the model, repository, service, schema, router, store, and domain-component layers. Dental is a gated overlay. **Core operates independently of Dental — demonstrated by dependency analysis (§1–§5) and by `test_architecture_boundary.py` + `test_industry_scoping.py`.**

---

## 9. Final Verification

### Changed files (this phase — test-only, zero production code)

| File | Change |
|---|---|
| `backend/app/tests/test_architecture_boundary.py` | **New.** 8 guard tests: no dental columns on Core tables; generic catalog does not import dental compat; Core/Dental module keys disjoint & subset of `ALL_MODULES`; non-dental templates leak no dental modules; dental template positively enables dental. |
| `backend/app/tests/test_industry_scoping.py` | Added explicit **403 direct-API** assertions on `/treatment-catalog/` for Insurance and Loan-Recovery tenants (completes item 10). |
| `frontend/src/store/__tests__/architectureBoundary.test.ts` | **New.** Static scan: no core store/component imports `pages/dental` or `components/dental`. |
| `docs/phase3_1_architecture_audit.md` | **New.** This document. |

No production modules, models, migrations, or UI were modified. No migrations were generated.

### Results

| Suite | Baseline (pre-change) | Final (with guards) | Verdict |
|---|---|---|---|
| Backend `pytest` | 1001 passed, **8 failed**, 13 skipped | 1009 passed, **8 failed**, 13 skipped | +8 new guard tests green; **0 new failures** |
| Frontend `vitest` | 237 passed | 239 passed (+2 guard) | +2 guard green; **0 new failures** |
| `tsc --noEmit` | PASS | PASS | ✅ |
| `npm run build` | PASS | PASS | ✅ |

### Pre-existing backend failures (8) — all infra/timing, none Core/Dental-related

- `test_feature_guard_cache::test_feature_guard_cache_flow` — cache/redis
- `test_hardening_redis_lock::test_redis_distributed_lock_basic` — needs Redis
- `test_lifespan_shutdown` (×2) — async loop shutdown timing
- `test_phase2_services::test_metadata_caching_invalidation` — cache timing
- `test_scheduled_reports_module::test_email_and_whatsapp_delivery_via_mocks` — delivery mocks
- `test_trial_requests` (×2) — public trial flow

These are unrelated to Phase 3.1 (no dental/core-genericity intersection) and predate this phase.

### Frontend suite flakes (non-deterministic, pre-existing)

Under the full parallel run, 2 dashboard-widget tests intermittently fail (observed: `KpiWidget` then `BranchesWidget` on separate runs — different files each time). Both pass deterministically in isolation. This is the known dashboard load-flake pattern, not a regression from this phase, and does not involve any Core/Dental code path.

**Baseline vs new:** 0 fixed, 0 newly broken. All added guard tests pass. Certification stands.
