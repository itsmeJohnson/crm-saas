# Phase 7 — Dynamic Forms · Implementation Report

> **Dynamic Forms is a WORK PACKAGE inside Phase 7. It is NOT a new phase or sub-phase.**

**Date:** 2026-08-20 · **Branch:** `feat/phase4-config-engine` (local, unpushed)
**Approach:** additive layer over the existing metadata stack — reuses `CustomFieldDefinition`, `MetadataValidationEngine`, and `DynamicCustomFields`. No new field system, no changes to record storage, no bypass of record validation.

---

## 1. Architecture

A **Form** is a tenant-owned **layout** for one entity (`lead`/`contact`/custom-object key): which fields, in what order, grouped into sections, with per-form `required`/`hidden`/`read_only` overrides. It never defines fields (those stay in `CustomFieldDefinition`) or stores values (those stay in records).

```
CustomFieldDefinition (field catalog)      MetadataValidationEngine (record gate)
        │                                            ▲
        │ referenced by key                          │ record submit unchanged
        ▼                                            │
FormDefinition.schema  ──►  FormRenderer  ──►  DynamicCustomFields (shared renderer)
 (sections→ordered keys                         (no second renderer)
  + overrides)
```

- **Config layer (FormService):** form existence, org ownership, entity compatibility, configured field set, presentation overrides.
- **Data layer (MetadataValidationEngine):** field existence, type/required/read-only/unique/entity_reference validation — **unchanged**, still authoritative. A form cannot loosen record validation (proven by test).

## 2. Files changed

**Backend (new):**
- `app/models/form_definition.py` — `FormDefinition` (org-scoped; `entity_type`, `key`, `name`, JSON `schema`, `is_active`, `is_default`, audit + soft-delete). Unique `(org, entity_type, key)` + index.
- `app/schemas/form_definition.py` — Create/Update/Response + typed `FormSchema`/`FormSection`/`FormFieldEntry` (JSON key `schema` preserved via alias).
- `app/services/form_service.py` — CRUD, admin-gated, org-scoped; entity allowlist (lead/contact/active object); **schema validated against active field definitions**; default-uniqueness; audit; `metadata_version` bump.
- `app/api/v1/forms.py` — `/api/v1/forms` router.
- `alembic/versions/d2e3f4a5b6c7_add_form_definitions.py` — additive, reversible, inspector-guarded migration.

**Backend (modified):** `app/models/__init__.py` (register model), `main.py` (register router), `app/tests/test_architecture_boundary.py` (guard forms modules).

**Frontend (new):**
- `services/formApi.ts` — typed client + `pickForm` (default→first).
- `components/forms/FormRenderer.tsx` — transforms definitions per the form (order/section/override/hide) and **reuses `DynamicCustomFields`**; falls back to raw definitions when no form.
- `pages/FormBuilderPage.tsx` — admin builder: entity select, field selection, order (up/down), sections, required/hidden/read-only overrides, default toggle, CRUD.

**Frontend (modified):** `components/objects/RecordFormModal.tsx` (use a form when present; unchanged when absent), `routes/moduleRegistry.ts` (`/forms` route).

**Tests (new):** `backend/app/tests/test_dynamic_forms.py`, `frontend/.../FormRenderer.test.tsx`, `frontend/.../FormBuilderPage.test.tsx`.

## 3. Database / migration

One additive table `form_definitions`. Migration `d2e3f4a5b6c7` (down_revision `c1d2e3f4a5b6`) — **single Alembic head**, inspector-guarded, reversible. **Verified on SQLite** (upgrade → idempotent → downgrade round-trip) **and real PostgreSQL 18.3** (correct UUID/VARCHAR/JSON/BOOLEAN types, unique constraint, indexes, idempotent, clean downgrade). No existing table touched.

## 4. API

```
GET    /api/v1/forms?entity_type=<t>[&include_inactive=]   # list (any active user)
POST   /api/v1/forms?entity_type=<t>                        # create (OrgAdmin)
GET    /api/v1/forms/{form_id}                              # read
PATCH  /api/v1/forms/{form_id}                              # update (OrgAdmin)
DELETE /api/v1/forms/{form_id}                              # soft-delete (OrgAdmin)
```
- Create/update body: `{ key, name, description?, schema, is_active?, is_default? }` (`schema` = `{sections:[{title,columns,fields:[{key,required?,hidden?,read_only?}]}]}`).
- Errors: unknown/inactive field → 400; foreign-entity field → 400; duplicate field in form → 400; unsupported entity → 400; duplicate form key → 400; non-admin → 403; cross-tenant → 404.

## 5. Security / tenant isolation

- Org-scoped everywhere (from the authenticated user); cross-tenant read/update/delete → 404.
- Manage = OrgAdmin/SuperAdmin; list/read = any active user (record perms still govern edits).
- **No field leakage:** a form may reference only active field keys of the **same entity + org** (validated on save) — cannot surface another entity's or tenant's fields.
- **No bypass:** record submission still goes through the existing record endpoints + `MetadataValidationEngine`; a form marking a field hidden/not-required **cannot** loosen record validation (test `test_form_does_not_bypass_record_validation`). Required overrides only tighten.

## 6. Backward compatibility

When **no** form exists for an entity, `FormRenderer` renders the raw definitions — the exact pre-Dynamic-Forms behavior. Lead/Contact/custom-object record flows are unchanged unless an admin opts in by creating a form.

## 7. Tests & results

**Backend `test_dynamic_forms.py` (13):** CRUD; sections/ordering/overrides persistence; unknown/duplicate/foreign field rejection; unsupported entity; custom-object form; duplicate form key; single-default-per-entity; non-admin 403; tenant isolation (list/get/update/delete 404); **no-bypass of record validation**; HTTP flow + serialization; API 403. → **all pass.**
**Architecture boundary (extended):** forms modules import no industry code → **pass.**
**Regression:** `test_custom_fields` + `test_custom_objects` → **51 pass** (Phase 4.1/4.2 intact).
**Frontend (10):** `applyForm` order/hide/override/safe-skip; `FormRenderer` layout + no-form fallback; `FormBuilderPage` build-schema-and-create + error. → **pass.** Full FE `vitest` **269 passed**, `tsc` **PASS**, `build` **PASS**.
**PostgreSQL:** migration verified on real PG 18.3.

## 8. Definition of Done — checklist

- [x] `form_definitions` schema implemented
- [x] migration implemented · [x] SQLite verified · [x] real PostgreSQL verified · [x] single Alembic head
- [x] backend service · [x] API · [x] authorization · [x] tenant isolation tested
- [x] form schema validation · [x] field ordering · [x] sections · [x] required / [x] hidden / [x] read-only overrides
- [x] Form Builder · [x] Form Renderer · [x] existing `DynamicCustomFields` reused
- [x] custom-object record forms work · [x] existing behavior works when no form exists
- [x] backend tests pass · [x] frontend tests pass · [x] TypeScript passes · [x] build passes
- [x] Phase 4.1 custom-field tests green · [x] Phase 4.2 custom-object tests green
- [x] security/isolation tests pass · [x] documentation · [x] no unrelated regressions (see §9)

## 9. Risks / notes

- Backend full-suite run carries the known pre-existing failures (redis/date-env) unrelated to this work — reported with the final numbers.
- MVP builder uses up/down ordering (no drag-and-drop dependency) and section-by-label grouping — deliberate, per plan.

## 10. Out of scope (unchanged from plan)

Form-driven **standard** lead/contact fields; conditional/branching visibility; multi-step wizards; drag-and-drop; form versioning/history; public form rendering; workflow-on-submit; report/table column layouts. These are **future work / class-A tasks**, not new phases.

---

> **Dynamic Forms is a WORK PACKAGE inside Phase 7. It is NOT a new phase or sub-phase.**
