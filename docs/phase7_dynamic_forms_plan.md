# Phase 7 — Dynamic Forms · Implementation Plan (READ-ONLY AUDIT)

> **Dynamic Forms is a WORK PACKAGE inside Phase 7. It is NOT a new phase or sub-phase.**

**Mode:** read-only audit + plan. No code/schema/migration/config changes; nothing committed, pushed, merged, or deployed.
**Date:** 2026-08-20 · **Roadmap position:** Phase 7 (Configurable CRM), Work Package 1 of 4.

---

## 1. Executive summary

The metadata stack from Custom Fields (WP-done) and Custom Objects (WP-done) already provides **fields, per-field flags (section/visible/read_only/required), a validation engine, and one generic renderer**. What is missing is the concept of a **Form**: a tenant-defined, named arrangement that **selects a subset of an entity's fields, orders them, groups them into sections, and applies per-form overrides** (required/hidden/read-only) — distinct from the *field catalog* and from a *record*. Dynamic Forms is a **thin additive layer**: **one new table** (`form_definitions`, JSON schema), a small service + API, a form-builder config UI, and a form-runtime renderer that **wraps the existing `DynamicCustomFields`**. No changes to `CustomFieldDefinition`, the validation engine, or record storage.

## 2. Current architecture (traced)

- **`CustomFieldDefinition`** (`backend/app/models/custom_field_definition.py`): `organization_id, entity_type, key, label, field_type, options, placeholder, description, default_value, validation_rules, section, is_active, read_only, visible, searchable, filterable, exportable, importable`. **No `display_order`** — the renderer orders by creation and groups by `section`.
- **Validation:** `MetadataValidationEngine.validate_and_sanitize(...)` — type-aware, rejects unknown keys, enforces required/read_only/unique/entity_reference, tenant-scoped. Reused by Lead, Contact, and Custom Object records (via `json_field="data"`).
- **Renderer:** `frontend/src/components/crm/DynamicCustomFields.tsx` — filters `is_active && visible` (plus optional `filter` prop), **groups by `section`**, renders all 13 types + errors. This is the reuse anchor.
- **Records/values:** `entity.custom_fields` JSON (Lead/Contact) and `custom_object_records.data` JSON. Values keyed by field `key`.
- **Config-object precedent:** `saved_filters` (`organization_id, user_id, name, entity_type, definition JSON, is_shared`) — the exact shape a form definition should follow.
- **Metadata delivery:** `/api/v1/metadata/bootstrap` (+`custom_fields_by_entity`, `custom_objects`), `metadataStore` (`customFields`, `customFieldsByEntity`, `customObjects`), `objectApi`/`metadataApi`.
- **Isolation:** every metadata/record query is `organization_id`-scoped from the authenticated user; cross-tenant → 404; admin-gated writes.

## 3. Existing capabilities (present — reuse)

| Capability | Where | Reuse for forms |
|---|---|---|
| Field catalog per entity | `CustomFieldDefinition` (`entity_type`) | forms reference field `key`s |
| 13 field types + validation | `custom_field_types`, `MetadataValidationEngine` | unchanged — server gate stays authoritative |
| Sections (single implicit grouping) | `CustomFieldDefinition.section` + renderer | forms provide explicit sections/order instead |
| Required / read_only / visible (global) | `validation_rules.required`, `read_only`, `visible` | forms **override** per form |
| One generic renderer | `DynamicCustomFields` | form runtime wraps it |
| Admin builders | `CustomFieldsManager`, `CustomObjectsPage` | form builder mirrors their pattern |
| Record CRUD + validation | lead/contact services, `CustomObjectRecordService` | form submit uses the **existing** record endpoints |

## 4. Missing capabilities (to build)

1. **A Form definition** — named, per-entity, tenant-scoped: which fields, in what order, in which sections, with per-form required/hidden/read-only overrides. **No table exists.**
2. **Explicit field ordering** — today ordering is implicit (creation). Forms store order in their schema (solves this **without** adding `display_order` to `CustomFieldDefinition`).
3. **Multiple forms per entity** (e.g., a create form vs edit form, or per-purpose) + a default.
4. **Form builder UI** (configuration) and **form runtime** (record entry driven by the form).
5. **Optional conditional visibility** (show field B if field A = X) — **out of scope for MVP** (see §17), architecture leaves room.

## 5. Reuse map

```
CustomFieldDefinition  ──(field catalog, unchanged)──┐
MetadataValidationEngine ─(server validation, unchanged)─┤
DynamicCustomFields ───(renderer, wrapped)───────────┐  │
                                                     │  │
NEW: form_definitions (schema: sections→ordered keys │  │
      + per-field overrides)  ───────────────────────┴──┴──►  FormRenderer → DynamicCustomFields
NEW: FormService / API  ───(CRUD + bootstrap)                 (record submit → existing record endpoints)
```

## 6. Proposed architecture

A **Form** = a tenant-owned layout document for one `entity_type` (a Core entity `lead`/`contact` **or** a custom-object key). It **does not** store field definitions (those stay in `CustomFieldDefinition`) and **does not** store values (those stay in records). It stores **selection + order + grouping + overrides**.

**Form `schema` (JSON):**
```json
{
  "sections": [
    { "title": "Basics", "columns": 2,
      "fields": [
        { "key": "budget", "required": true },
        { "key": "property_type", "hidden": false, "read_only": false }
      ] }
  ]
}
```
- Order = array order (sections, then fields). Overrides (`required`/`hidden`/`read_only`) are **per-form**, layered over the field definition at render/validate time.
- Only field `key`s that exist + are active for the entity are valid (validated on save).

**Runtime:** the form runtime resolves each `key` → its `CustomFieldDefinition`, applies form overrides, and hands the ordered/sectioned list to `DynamicCustomFields`. **Submission uses the existing record endpoints** (lead/contact update, `/objects/{key}/records`), so the `MetadataValidationEngine` remains the single server-side gate.

## 7. Database changes (additive only — do NOT create now)

**One new table** `form_definitions`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | BaseModel |
| `organization_id` | UUID FK, indexed | tenant scope |
| `entity_type` | String(50), indexed | `lead`/`contact`/`<object_key>` |
| `key` | String(80) | machine key, unique per (org, entity_type) |
| `name` | String(150) | display |
| `description` | String(500) null | |
| `schema` | JSON | sections + ordered fields + overrides |
| `is_active` | bool | |
| `is_default` | bool | one default per (org, entity_type) |
| `created_by`/`updated_by` | UUID FK | |
| `created_at`/`updated_at`/`is_deleted`/`deleted_at` | BaseModel | soft delete |

- `UniqueConstraint(organization_id, entity_type, key)`; index `(organization_id, entity_type, is_active)`.
- **No changes to `custom_field_definitions` or record tables.** No `display_order` added (order lives in the form schema).
- Migration: **additive, reversible, inspector-guarded** (same pattern as `c1d2e3f4a5b6`). Head becomes a single new revision after `c1d2e3f4a5b6`.

## 8. Backend changes (minimum)

- `models/form_definition.py` — `FormDefinition` (as §7). Register in `models/__init__.py`.
- `schemas/form_definition.py` — Create/Update/Response + a `schema` validator (sections/fields shape).
- `services/form_service.py` — org-scoped CRUD; admin-gated; **validate schema keys against active `CustomFieldDefinition`s for the entity**; enforce one `is_default` per (org, entity_type); audit via `AuditService`; reject entity_type not in `SUPPORTED_ENTITY_TYPES ∪ active object keys` (reuse `reserved_fields` + object lookup, same as `CustomFieldService`).
- `api/v1/forms.py` — router (see §10); register in `main.py`.
- `bootstrap` — include the org's active forms (eager, lightweight) or expose `GET /forms?entity_type=` for lazy load (recommended lazy, like object fields).
- **No new validation engine** — record submission keeps using `MetadataValidationEngine`. Optional hardening: server may reject submitted keys not exposed by the form when a form is specified (a form-scoping guard) — see §11.

## 9. Frontend changes

- `services/formApi.ts` — CRUD + list by entity.
- `store/metadataStore.ts` — hold `formsByEntity` (or lazy fetch).
- **Form builder (config UI)** — `pages/.../FormBuilder` (mirrors `CustomObjectsPage`/`CustomFieldsManager`): pick entity → pick fields from the catalog → arrange (order + sections) → set per-field required/hidden/read-only → save → set default/active. **Drag/drop:** none exists today; MVP can use up/down move buttons (no new dependency), drag/drop as an enhancement.
- **Form runtime** — `components/forms/FormRenderer.tsx`: given `entity_type` + optional `formKey`, load the form + the entity's definitions, apply overrides, render via **existing `DynamicCustomFields`**, submit via existing record endpoints.
- **Integration:** custom-object `RecordFormModal` and the lead/contact custom-field sections opt into a form when one exists; otherwise fall back to today's default (all visible+active fields) — **fully backward compatible**.

## 10. API contract (proposed)

```
GET    /api/v1/forms?entity_type=<t>                 # list forms for entity (active)
POST   /api/v1/forms?entity_type=<t>                 # create (OrgAdmin)
GET    /api/v1/forms/{form_id}                        # read
PATCH  /api/v1/forms/{form_id}                        # update (OrgAdmin)
DELETE /api/v1/forms/{form_id}                        # soft-delete (OrgAdmin)
# (optional) POST /api/v1/forms/{form_id}/default     # set as default for its entity
```
- Request (create): `{ key, name, description?, schema, is_active?, is_default? }`.
- `schema` validated server-side: every field key exists + is active for `entity_type`; unknown keys → 400; duplicate key in schema → 400.
- Response: full form incl. `schema`, timestamps.
- **Record create/edit is unchanged** — forms are a view layer over existing record endpoints; no new submission endpoint.

## 11. Security / tenant isolation

- **Tenant/org isolation:** every form query `organization_id`-scoped from the authenticated user; cross-tenant read/update/delete → 404 (mirror `CustomObjectService`).
- **Authorization:** manage forms = OrgAdmin/SuperAdmin; render/use = any active user (record permissions still govern the underlying create/edit).
- **No field leakage:** a form only references keys that are active `CustomFieldDefinition`s for the entity **in the same org** (validated on save); it cannot surface another entity's or tenant's fields.
- **No over-submission:** the `MetadataValidationEngine` already rejects keys not defined for the entity, and enforces `read_only`. **Optional form-scoping guard:** when a record is submitted "through" a form, the server may additionally reject keys the form marks `hidden`/absent (defense-in-depth). MVP relies on the engine; the guard is a documented option.
- **Required-override safety:** a form marking a field required tightens (never loosens) validation; server still enforces the definition's own rules.
- **Tests required:** cross-tenant form 404; form referencing a foreign/nonexistent field rejected; non-admin cannot manage; read_only/hidden respected on submit; default-uniqueness per entity.

## 12. Performance considerations

- Forms are small JSON docs, few per entity. **Load lazily per entity** (like custom-object fields) or include active forms in `bootstrap` if small. Cache alongside metadata; **invalidate + bump `metadata_version` on form mutation** (reuse `MetadataCacheService`, same as custom fields). No JSONB querying needed (forms aren't filtered by content). **Do not over-engineer** — no versioning table, no per-render DB joins beyond the definition fetch already done.

## 13. Testing strategy

**Backend (`test_dynamic_forms.py`):** form CRUD; schema validation (valid keys, unknown-key reject, duplicate-key reject); entity allowlist (lead/contact/object; reject unknown/foreign entity); default-uniqueness per (org, entity); tenant isolation (A's form invisible to B; cross-tenant 404); non-admin blocked (403); read_only/hidden override respected on record submit through a form; inactive form not returned; concurrent update (last-write-wins + version bump).
**Frontend:** `FormRenderer` renders ordered sections + fields, applies overrides, validates, create+edit, empty/default (no form → fallback to all-visible), API integration (mocked); `FormBuilder` — add/reorder/section/override/save.
**Regression (must stay green):** `test_custom_fields`, `test_custom_objects`, `test_architecture_boundary`, `test_industry_scoping`; existing Lead/Contact modals and custom-object `RecordFormModal` still work when **no** form is defined; FE `vitest`/`tsc`/`build`.

## 14. Definition of Done (this work package ONLY)

- [ ] `form_definitions` table via one additive, reversible, inspector-guarded migration; single Alembic head; verified on SQLite **and** real PostgreSQL.
- [ ] `FormService` + API: org-scoped CRUD, admin-gated, schema validated against active field definitions, default-uniqueness, audited.
- [ ] Forms exposed to the frontend (lazy per entity or bootstrap) + `metadataStore` wiring; cache invalidation + `metadata_version` bump on mutation.
- [ ] `FormRenderer` reuses `DynamicCustomFields`; record submit goes through **existing** record endpoints; **no** form → unchanged current behavior (backward compatible).
- [ ] `FormBuilder` config UI: select/reorder/section/override/save/set-default, generic (no industry terms).
- [ ] Works for `lead`, `contact`, and a custom object.
- [ ] Security proven by tests (tenant isolation, non-admin block, read_only/hidden, no field leakage).
- [ ] Full regression green (BE pytest new+existing; FE vitest/tsc/build) with only the known env flakes.
- [ ] Architecture boundary guard extended to the forms modules (no industry imports).
- [ ] Plan + implementation report docs.

**When all boxes pass → Work Package 1 (Dynamic Forms) COMPLETE.** No "Phase 7.1"; this is a task inside Phase 7.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Scope creep into full form-driven **standard** fields (first_name, etc.) | Out of scope (§17); MVP governs custom-field layout + custom-object records |
| Conditional visibility demand | Out of scope MVP; schema leaves room (`when` clause) — class-A future task, not a phase |
| Over-submission / read_only bypass | Engine already enforces; optional form-scoping guard + tests |
| Drag/drop expectation | MVP uses move buttons; drag/drop is an enhancement (no new dep) |
| Divergent-from-prod branch (`cc146e0` unmerged) | Build on `feat/phase4-config-engine`; production gate handled separately (Phase 8) |

## 16. Implementation order

1. Backend model + migration (SQLite+PG verified).
2. Schema + `FormService` + API + validation + audit + cache.
3. Bootstrap/list wiring + `formApi` + `metadataStore`.
4. `FormRenderer` (wrap `DynamicCustomFields`) + integrate into `RecordFormModal` + lead/contact custom sections (fallback-safe).
5. `FormBuilder` config UI.
6. Backend + frontend tests + boundary guard.
7. Full regression + docs.

## 17. Explicitly OUT OF SCOPE (WP1)

- Form-driven **standard/first-class** fields (Lead.first_name, etc. stay hardcoded in modals).
- Conditional/branching visibility rules.
- Multi-step/wizard forms; drag-and-drop builder (move-buttons MVP).
- Form versioning/history table.
- Public/anonymous form rendering (that's Lead Capture, already separate).
- Workflow/automation on submit.
- Report/table **column layouts** (a different concern; not this WP).

## 18. Roadmap position

Phase 7 (Configurable CRM), **Work Package 1 of 4** (Dynamic Forms → Pipeline/Stage Builder → Industry Template Builder → Configurable CRM QA). Building on Custom Fields + Custom Objects (both done).

---

## Architectural decisions requiring your approval

1. **Storage:** single `form_definitions` table with a JSON `schema` (recommended, consistent with `saved_filters`/records) **vs** normalized `form` + `form_fields` tables. *(Rec: JSON single table.)*
2. **Ordering:** store order in the form `schema`, leave `CustomFieldDefinition` untouched (recommended) **vs** add a global `display_order` column. *(Rec: form schema.)*
3. **MVP scope:** forms govern **custom-field layout + custom-object records** (recommended) **vs** also refactor standard lead/contact fields to be form-driven now (larger). *(Rec: custom scope for WP1.)*
4. **Versioning:** none for MVP (overwrite-in-place + `metadata_version` bump) **vs** a versioned form history. *(Rec: none.)*
5. **Form-scoping guard:** rely on the existing engine (recommended) **vs** also reject hidden/undefined keys at submit when a form is used. *(Rec: engine + tests; add guard only if you want defense-in-depth.)*

> **Dynamic Forms is a WORK PACKAGE inside Phase 7. It is NOT a new phase or sub-phase.**

*Audit + plan only. No implementation, schema, migration, code, config, commit, push, PR, or deploy performed. Awaiting review before any implementation.*
