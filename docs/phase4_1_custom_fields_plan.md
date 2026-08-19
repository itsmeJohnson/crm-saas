# Phase 4.1 — Custom Fields Engine · Implementation Plan

**Date:** 2026-08-19
**Status:** PLAN ONLY — no code written. Awaiting review before implementation.
**Author note:** Step 0 (read-only audit) is complete. The single most important finding is below.

---

## ⚠️ Headline finding — the engine already exists

A production-grade, tenant-scoped Custom Fields Engine is **already implemented and wired in**. This phase must **extend and harden the existing system, not build a competing one.** Building a parallel `CustomFieldService`/`DynamicField` would be a direct violation of the prompt's "if functionality already exists, extend/refactor it."

### What already exists (verified, file-by-file)

| Layer | Artifact | State |
|---|---|---|
| Model | `backend/app/models/custom_field_definition.py` — `CustomFieldDefinition` | ✅ Rich: `organization_id, entity_type, key, label, field_type, options, placeholder, description, default_value, validation_rules, section, is_active, read_only, visible, searchable, filterable, exportable, importable, created_by, updated_by`. Unique constraint `(organization_id, entity_type, key)`. Soft-delete via `is_deleted`. |
| Storage | `custom_fields` JSON column | ✅ On **`leads`** and **`contacts`** only |
| Service | `backend/app/services/custom_field_service.py` — `CustomFieldService` | ✅ `list_definitions / create_definition / update_definition / delete_definition` (soft), admin-gated, org-scoped, cached, audited, metadata-versioned, unique-key enforced |
| Validation | `backend/app/services/metadata_validation_engine.py` — `MetadataValidationEngine.validate_and_sanitize` | ✅ Unknown-key reject, required, normalize (trim/email/phone), defaults, read-only, text (min/max/regex), number (min/max), date (YYYY-MM-DD), select (in options), checkbox (bool coerce), unique (DB) |
| Cache | `backend/app/services/metadata_cache_service.py` | ✅ Per-org/entity cache + metadata_version bump/invalidate |
| Schema | `backend/app/schemas/custom_field.py` | ✅ Create/Update/Response; `key` pattern `^[a-z0-9_]+$` |
| API | `backend/app/api/v1/metadata.py` | ✅ `GET /bootstrap`, `GET/POST /metadata/custom-fields?entity_type=`, `PATCH/DELETE /metadata/custom-fields/{id}` |
| Migration | `alembic/versions/metadata_engine_0001_add_metadata_engine.py` | ✅ `custom_field_definitions` table already created |
| FE store | `frontend/src/store/metadataStore.ts` + `services/metadataApi.ts` | ✅ Typed `CustomFieldDefinition`, `bootstrap()`, CRUD client |
| FE renderer | `frontend/src/components/crm/DynamicCustomFields.tsx` | ✅ Generic, section-grouped: text/number/date/select/checkbox |
| FE admin | `frontend/src/components/crm/CustomFieldsManager.tsx`, `LeadCustomFieldsManager.tsx` | ✅ Create/list/delete; offers 5 types; options = comma string |
| FE integration | `LeadModal.tsx`, `ContactModal.tsx`, `ImportModal.tsx`, `MappingPreview.tsx`, `LeadsPage.tsx`, `ContactsPage.tsx` | ✅ Custom fields already appear in Lead + Contact forms and import mapping |
| Tests | `test_phase4_leads.py`, `test_contact_module.py`, `test_phase2_services.py`, `test_lead_capture.py` | ✅ Exercise custom fields on leads/contacts |

**Conclusion:** ~80% of the prompt's Steps 2–14 are already delivered for **Lead** and partially for **Contact**. Phase 4.1's real work is a focused **gap-closure** pass.

---

## Gap analysis (this is the actual Phase 4.1 scope)

| # | Gap | Where | Severity | Needs migration? |
|---|---|---|---|---|
| G1 | **Field-type coverage is 5, prompt wants 13.** Missing: `textarea, currency, percentage, datetime, boolean, email, phone, url, multiselect` | validation engine + FE renderer + schema doc + type enums | High | **No** (field_type is a string in existing columns) |
| G2 | **Contact validation is weaker than Lead.** Contact uses `contact_service._validate_custom_fields` (key-existence only); Lead uses the full type-aware engine | `contact_service.py` | High | No |
| G3 | **No reserved-key registry.** A tenant can define `key="email"`, `"phone"`, `"id"`, colliding with first-class columns | new `core/` module + `create_definition` | High | No |
| G4 | **No entity_type allowlist.** `create_definition` accepts any `entity_type` string (e.g. `"patient"`), including entities with no storage column | service + schema | Medium | No |
| G5 | **`options` is `list[str]`, prompt wants `{value,label}[]`** with stable value / editable label | schema + engine + renderer + admin | Medium | No (JSON column tolerant; needs back-compat coercion) |
| G6 | **`multiselect` has no storage/validation semantics** (array of values ⊆ option values) | engine + renderer | Medium | No |
| G7 | **Bootstrap returns custom_fields for `lead` only.** Contact defs not in bootstrap; no per-entity map | `metadata.py` bootstrap | Medium | No |
| G8 | **Admin builder is per-page (Leads/Contacts), no central Settings → Custom Fields** with entity selector | new FE page + registry route | Low | No |
| G9 | **No read-only "Additional Information" detail block** distinct from the editable form renderer | small FE component | Low | No |
| G10 | **Latent bug:** validation engine `isinstance(val, (datetime, datetime.date))` — `datetime.date` is invalid (`datetime` imported as class) | `metadata_validation_engine.py` | Low (string path unaffected) | No |
| G11 | **`customer`, `task`, `opportunity` have no `custom_fields` column** | models + migration | Deferred | **Yes (if pursued)** |

---

## 1. Current architecture findings

- **Storage model is correct and already in place:** definitions in `custom_field_definitions`; values in `entity.custom_fields` JSON keyed by `key`. The mandated separation (Step 3) is honored. No industry columns exist on Core models (re-verified: only `leads`, `contacts` carry `custom_fields`; zero `patient_id/policy_id/...`).
- **Tenant isolation is enforced correctly:** every service query filters `organization_id == actor.organization_id`; `_get_owned` returns 404 cross-tenant; `organization_id` is taken from the authenticated `User`, never the client.
- **Permissions reuse the existing system:** `require_role(["OrgAdmin"])` on write endpoints + `_ensure_admin` in the service. Read via `require_active_user`.
- **Bootstrap/metadata mechanism exists:** `GET /metadata/bootstrap` returns `metadata_version + custom_fields (lead) + pipelines + crm_config`; frontend `metadataStore` consumes it. Cache invalidation + `metadata_version` bump on every definition mutation.
- **Industry-neutrality holds:** the engine lives entirely in CRM Core; it imports no dental/industry modules. (Phase 3.1 guard `test_architecture_boundary.py` already protects the Core boundary.)

## 2. Existing reusable infrastructure (reuse, do not recreate)

`CustomFieldService`, `MetadataValidationEngine`, `MetadataCacheService`, `AuditService`, `custom_field.py` schemas, `metadata.py` router, `metadataStore`, `metadataApi`, `DynamicCustomFields`, `CustomFieldsManager`, `require_role`/`require_active_user`. **All extension happens inside these.**

## 3. Proposed schema

**No new table. No new columns for the lead+contact scope.** `CustomFieldDefinition` already has every attribute the prompt lists. Changes are **semantic/string-level**, fully absorbed by existing JSON columns:

- `field_type`: widen the accepted set (string column — no DDL). Introduce a backend `CustomFieldType` enum + a FE union type as the source of truth.
- `options`: evolve to a normalized shape `[{ "value": str, "label": str }]`, while **accepting legacy `["a","b"]` and coercing** `"a" → {value:"a",label:"a"}` on read. Stored JSON stays compatible.
- (Deferred G11) adding `customer.custom_fields` / `task.custom_fields` would each be an additive, nullable JSONB column via one reversible migration — **out of the default 4.1 scope**; see §14.

## 4. Backend architecture

1. `backend/app/core/custom_field_types.py` (new): `CustomFieldType` enum + a `FIELD_TYPE_SPECS` registry mapping each type → `{storage, validate, normalize, serialize}` hooks. The validation engine dispatches through this registry instead of an `if/elif` ladder.
2. `backend/app/core/reserved_fields.py` (new): `RESERVED_KEYS: dict[entity_type, set[str]]` + `SUPPORTED_ENTITY_TYPES` allowlist. Single source of truth (Step "central reserved-field registry").
3. Extend `MetadataValidationEngine` with the new types (currency/percentage → numeric with constraints; datetime → ISO-8601; email/phone/url → format regex; boolean → coerce; multiselect → list ⊆ option values; textarea → text). Fix G10.
4. Extend `CustomFieldService.create_definition` to reject reserved keys (G3) and unknown entity types (G4).
5. Unify `ContactService` custom-field handling onto `MetadataValidationEngine.validate_and_sanitize` (G2), matching the Lead path (create + update).
6. Extend `bootstrap` to return `custom_fields_by_entity: {lead:[...], contact:[...]}` **in addition to** the existing flat `custom_fields` (kept for back-compat) (G7).

## 5. API design

Keep the **existing, already-integrated** routes (do not rename — the frontend depends on them):
- `GET /metadata/custom-fields?entity_type=<t>` · `POST` (OrgAdmin) · `PATCH /{id}` (OrgAdmin) · `DELETE /{id}` (OrgAdmin, soft) · `GET /metadata/bootstrap`.
- Add validation: `entity_type` must be in `SUPPORTED_ENTITY_TYPES` else `422/400`.
- The prompt's `/custom-fields/{entity_type}` path style is **noted but not adopted** — the query-param form is the established convention and is wired into `metadataApi.ts`. (Documented deviation.)

## 6. Permission model

Unchanged, reused: **manage definitions** = OrgAdmin/SuperAdmin (`_ensure_admin` + `require_role(["OrgAdmin"])`); **read definitions** = any active user; **edit values** = governed by the entity's own create/update permissions (lead/contact). No second authz system.

## 7. Validation strategy

Server-side authoritative via `MetadataValidationEngine`, dispatched through `FIELD_TYPE_SPECS`. Structured errors: evolve `MetadataValidationError` to optionally carry `{field, code, message}` (the prompt's shape) while preserving the current string message for back-compat. Frontend performs light UX validation only; server is the gate.

## 8. Frontend architecture

- Extend `CustomFieldType` union + `options` type to `{value,label}[]` (accept `string[]` legacy) in `metadataApi.ts`.
- Extend `DynamicCustomFields.tsx` with renderers for the new types (textarea, currency, percentage, datetime, boolean/switch, email, phone, url, multiselect). **One generic component — no per-industry components.**
- Add a read-only `CustomFieldsDisplay.tsx` for detail views ("Additional Information"), rendering from definitions + values with per-type formatting (G9).
- Add a central **Settings → Custom Fields** page with an entity selector, reusing `CustomFieldsManager` logic; register its route in `moduleRegistry.ts` under `admin_core`/settings (G8). Keep existing per-page managers working.
- Extend `metadataStore` to hold `customFieldsByEntity` from bootstrap.

## 9. Tenant isolation strategy

No change to the enforced pattern (org-scoped queries, server-derived `organization_id`, 404 cross-tenant). New tests will prove Tenant A's `budget` is invisible to Tenant B and vice-versa across definition read/update/delete and value storage/retrieval.

## 10. Migration strategy

- **Default 4.1 scope (lead + contact): NO migration** — field-type widening, reserved keys, entity allowlist, options shape, and contact-unification are all code-only over existing columns/tables.
- If G11 (customer/task custom fields) is approved, one additive migration adding nullable JSON columns — reversible, non-destructive, no data transform. Kept **out** of the default plan.

## 11. Backward compatibility strategy

- Existing stored `custom_fields` values: **untouched**. New validation is a superset; existing 5 types behave identically.
- Legacy `options: string[]`: coerced to `{value,label}` on read; still accepted on write.
- Bootstrap keeps the flat `custom_fields` field; adds the per-entity map alongside.
- Existing API routes unchanged. Existing FE managers keep working.
- Contact unification must not reject values that the old key-only check allowed **unless** they genuinely violate a definition's type/rules — call out in tests as an intentional tightening; verify against current fixtures.

## 12. Testing strategy

- Backend `test_custom_fields.py` (new): CRUD, tenant isolation, duplicate keys, **reserved keys**, **entity_type allowlist**, invalid types, invalid options, required, min/max, select/multiselect, currency/percentage/date/datetime/email/phone/url, permission enforcement, contact parity with lead.
- Extend Phase 3.1 guard `test_architecture_boundary.py`: assert `custom_field_service`, `metadata_validation_engine`, `custom_field_definition`, `reserved_fields`, `custom_field_types` import **no** industry module.
- Frontend: `DynamicCustomFields.test.tsx` (all field types, required, errors, multiselect, read-only), `CustomFieldsManager.test.tsx` (entity select, options editor, new types), `CustomFieldsDisplay.test.tsx` (formatting, empty state).
- Regression: full backend `pytest`, `vitest`, `tsc`, `build` with baseline vs final delta (baseline is the Phase 3.1 numbers: BE 1009 passed / 8 pre-existing infra failures; FE 239 passed + 2 known flakes).

## 13. Rollout strategy

Additive and dark-launchable: new field types are opt-in per definition; existing tenants see no change until an admin creates a field of a new type. No data backfill. Ship behind normal deploy; the metadata_version/cache path already forces clients to refresh definitions.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Contact-unification tightens validation and breaks an existing fixture/tenant value | Run full suite; diff failures; only adjust tests after proving against real behavior; treat as intentional and documented |
| `options` shape change ripples to import/export/filter surfaces (7 lead surfaces already consume defs) | Coercion layer accepts both shapes; audit each consumer before merge |
| Scope creep into Custom Objects / new entities | Hard non-goal; G11 explicitly deferred |
| Bootstrap contract change breaks FE | Add fields, never remove; keep flat `custom_fields` |
| Latent date bug (G10) masks a real datetime path once `datetime` type added | Fix G10 as part of G1 |

## 15. Explicit non-goals (Phase 4.1)

Custom Objects; Property/Policy/Loan/Patient/Claims entities; advanced relationship fields (`entity_reference`/`user` beyond stubbed extension points); workflow/email/WhatsApp automation; ads integrations; advanced reporting/AI; mobile redesign; full drag-and-drop form builder; custom dashboards; **full JSONB custom-field search/filter query engine** (design-for, don't build — see below); adding `custom_fields` to customer/task/opportunity (G11, deferred to 4.1b/4.2).

**Search/filter (Step 13):** not built now. Storage + `searchable`/`filterable` flags already make future `?custom_fields[budget][gte]=...` feasible. Deferred to Phase 4.x.

---

## Recommended decision points for your review

1. **Entity scope:** confirm Phase 4.1 = **Lead + Contact only** (zero migration). Customer/Task (G11) deferred? (Recommended: yes, defer.)
2. **Options shape:** adopt `{value,label}[]` with legacy coercion? (Recommended: yes.)
3. **API path:** keep the established `?entity_type=` query convention rather than the prompt's `/custom-fields/{entity_type}`? (Recommended: keep.)
4. **Field-type set:** implement all 13 now, or prioritize the industry-driving subset (currency, select, multiselect, date, datetime, email, phone, url, textarea) first? (Recommended: all 13 — low incremental cost once the registry exists.)

---

**STOP.** Per the Phase 4.1 instructions, implementation halts here pending review of this plan. No production code, schemas, migrations, or tests have been modified in this step.
