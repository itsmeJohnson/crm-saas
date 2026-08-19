# Phase 4.2 — Custom Objects · Architecture Audit & Implementation Plan

**Date:** 2026-08-19
**Status:** PLAN ONLY — no code written. Awaiting review before implementation.
**Builds on:** Phase 4.1 Custom Fields Engine. Reuse it; do not fork it.

---

## ⭐ Core question answered first

> *Can the existing `CustomFieldDefinition` model be extended to support Custom Objects (Property, Policy, Loan…) without breaking Lead/Contact?*

**Yes — cleanly, with no change to the `custom_field_definitions` schema.** The mechanism is the column that already exists: **`entity_type`**.

- Today `entity_type ∈ {"lead", "contact"}` (a free `String(50)` column with an allowlist in `core/reserved_fields.py`).
- For a custom object, `entity_type` becomes that object's **`key`** (e.g. `"property"`). Fields attach to an object exactly the way they attach to Lead/Contact — same table, same `MetadataValidationEngine`, same `DynamicCustomFields` renderer.
- **The only change is that the allowlist stops being a static set** and becomes "core entities (`lead`, `contact`) **plus** the org's active custom-object keys." That check moves from a pure function to an async lookup (the create path is already async — low risk).

This is the whole reason Phase 4.1 was sequenced first: Custom Objects are "a named container + a set of `CustomFieldDefinition`s scoped to that name + a JSON record store." ~70% of the machinery already exists.

---

## 1. Audit — existing foundation to REUSE (not rebuild)

| Capability | Existing artifact | Reuse for Custom Objects |
|---|---|---|
| Field definitions | `CustomFieldDefinition` (`entity_type` string) | Attach object fields via `entity_type = <object key>` — **no new field table** |
| Field validation | `MetadataValidationEngine.validate_and_sanitize` | Validate record `data` against the object's field defs (already generic over `model_class`) |
| Field types + options | `core/custom_field_types.py` | Unchanged; `entity_reference` becomes the relationship type |
| Reserved keys / entity allowlist | `core/reserved_fields.py` | Extend: dynamic supported-entity check; base reserved keys for records |
| Generic tenant CRUD | `repositories/base.py` → `TenantRepository[Model]` (fail-closed org scoping) | Base for `CustomObjectRecordRepository` |
| Soft delete | `models/base.py` `BaseModel` (`is_deleted`, `deleted_at`) | Records + definitions inherit it |
| Audit history | `AuditService.log_event(...)` | Record create/update/delete events |
| Caching + versioning | `MetadataCacheService` (per-org, `metadata_version` bump) | Cache object definitions + their field defs |
| Dynamic JSON filtering | `lead_repository.py:138` `model.custom_fields[key].as_string().ilike(...)` | **Precedent** for the record query engine — but only substring today (see §11) |
| Import framework | `services/import_/` (csv/excel/google-sheets parsers, `header_mapper`, `validation_engine`, `template_generator`) | Record import/export |
| Permission enforcement | `PermissionService`, `require_role`, `enforce_resource(...)` | Object + record permissions |
| Frontend renderer | `components/crm/DynamicCustomFields.tsx` | Record forms — one renderer, already all 13 types |
| Frontend builder | `CustomFieldsManager.tsx` (`entity_type` param) | Attach fields to an object by passing the object key |
| Frontend metadata | `store/metadataStore.ts` (`customFieldsByEntity`) | Add `customObjects` + per-object field maps |
| Module registry | `routes/moduleRegistry.ts` (single registry) | Object routes as generic entries |

**Greenfield (new) parts:** two tables (`custom_object_definitions`, `custom_object_records`), a record service/repository, a generic records API, the operator-based query engine, and the frontend object manager + dynamic record table/form. **No competing metadata system.**

**Confirmed by audit:** no existing `custom_object*` / record scaffolding exists (grep clean), so there is nothing to collide with.

## 2. Custom Object definitions

New table `custom_object_definitions`:

| Column | Notes |
|---|---|
| `id`, `created_at`, `updated_at`, `is_deleted`, `deleted_at` | from `BaseModel` |
| `organization_id` | tenant scope |
| `key` | machine key, unique per org, `^[a-z][a-z0-9_]*$`; **must not collide** with `lead`/`contact`/reserved entity names or another object key |
| `label`, `label_plural` | display |
| `icon`, `description`, `color` | UI |
| `is_active`, `is_system` | lifecycle |
| `display_field_key` | which field is the record's title (fallback: first text field) |
| `created_by`, `updated_by` | audit |

Fields attach via existing `CustomFieldDefinition` with `entity_type = definition.key`. **Reserved entity keys** (`lead`, `contact`, plus system words) are rejected as object keys.

## 3. Custom Object records

New table `custom_object_records` (single shared table — **not** per-object physical tables):

| Column | Notes |
|---|---|
| `id`, `created_at`, `updated_at`, `is_deleted`, `deleted_at` | `BaseModel` (soft delete built in) |
| `organization_id` | tenant scope, indexed |
| `object_definition_id` | FK → `custom_object_definitions`, indexed |
| `data` | JSON (JSONB on Postgres) — values keyed by field_key, **identical pattern to `entity.custom_fields`** |
| `created_by`, `updated_by` | audit |

**Why one shared JSONB table, not dynamic per-object tables:** dynamic `CREATE TABLE`/`ALTER TABLE` per tenant-object is a multitenancy and migration hazard (schema drift, migration explosion, connection-pool DDL locks). A shared JSON table matches the proven Lead/Contact `custom_fields` model and keeps migrations static. Index strategy in §16.

## 4. Tenant isolation

Reuse `TenantRepository` (fails closed without an org id). Every record/definition query filters `organization_id == actor.organization_id`; cross-tenant access → 404. New guard tests mirror the Phase 4.1 isolation tests (Tenant A's `property` object + records invisible to Tenant B).

## 5. Object permissions

Reuse the existing system — **no second authz layer**:
- **Manage object definitions & fields:** OrgAdmin/SuperAdmin (as custom fields today).
- **Record CRUD:** generic resource `custom_object:<key>` enforced through `PermissionService`/`enforce_resource`, so per-object view/create/edit/delete grants ride the existing custom-role machinery. Default: any active user can CRUD records of active objects unless a custom role restricts it.

## 6. Dynamic schemas & 7. Field attachment

An object's "schema" = its `CustomFieldDefinition` rows (`entity_type = key`). Adding a field = creating a definition against the object key — the **exact** admin flow that exists for Lead/Contact. `MetadataValidationEngine` validates record `data` against them. Zero new validation code.

## 8. Relationships between objects

Implement via the field type **`entity_reference`** (the Phase 4.1 extension-point stub):
- Stored in record `data` as `{ "target": "<object_key>", "id": "<record_uuid>" }` (or an array for one-to-many).
- Validation: target object exists + is active for the tenant; referenced record exists + same org.
- `option`-style metadata on the definition names the target object.

**Scope decision for review:** implement single + multi `entity_reference` (covers "a Loan belongs to a Customer", "a Property has many Viewings"). **Defer** a separate typed `custom_object_relationships` join-table graph (bidirectional cascade rules, M2M with attributes) to Phase 4.2b unless you want it now.

## 9. Generic CRUD APIs

One generic router (mirrors the `?entity_type=` convention already established):

```
# Definitions (OrgAdmin)
GET/POST            /api/v1/objects
GET/PATCH/DELETE    /api/v1/objects/{object_key}
# Fields — reuse existing custom-fields endpoints with entity_type=<object_key>
GET/POST            /api/v1/metadata/custom-fields?entity_type=<object_key>
# Records (generic, permission-gated per object)
GET                 /api/v1/objects/{object_key}/records      # list + filter + sort + paginate
POST                /api/v1/objects/{object_key}/records
GET/PATCH/DELETE    /api/v1/objects/{object_key}/records/{id} # DELETE = soft
```

No per-industry endpoints. `bootstrap` exposes object definitions; **field defs load lazily per object** (see §16 — do not bloat bootstrap with every object's fields).

## 10. Frontend object manager & dynamic record tables/forms

- **Object manager** (Settings): create/edit objects, then attach fields by reusing `CustomFieldsManager` with `entityType = object.key`.
- **Dynamic record form:** reuse `DynamicCustomFields` (all 13 types already) — record `data` in, sanitized out.
- **Dynamic record table:** columns from the object's `filterable`/`visible` field defs; render via a generic table; row → record form.
- **Store:** `metadataStore` gains `customObjects` and a per-object field cache; `moduleRegistry` renders object routes generically.
- No `PropertyTable.tsx` / `PolicyForm.tsx` — one generic set.

## 11. Search / filter / sort — the JSONB query engine (prioritized, per your guidance)

Today's filtering is **substring `ilike` only** (`lead_repository.py:138`). Custom Objects need real operators. Proposed **bounded operator set** for 4.2:

```
GET /api/v1/objects/property/records?filters=[
  {"field":"property_type","op":"eq","value":"Commercial"},
  {"field":"value","op":"gte","value":10000000}
]&sort=value:desc&page=1&page_size=50
```

Operators: `eq, ne, gt, gte, lt, lte, contains, startswith, in, is_empty`.

**Cross-DB translation (critical):** the project runs SQLite in tests, Postgres in prod.
- Text ops: `record.data[field].as_string()` (SQLAlchemy JSON indexing — works on both) + `ilike`/`==`.
- Numeric/date ops: `cast(record.data[field].as_string(), Numeric/DateTime)` then compare. On Postgres this compiles to `(data->>'field')::numeric`; on SQLite to `CAST(json_extract(data,'$.field') AS ...)`. A small `build_record_filter(defs, filters)` helper centralizes the field_type → cast mapping (using the object's field definitions to know each field's type — so `value` is known-numeric).
- Guardrails: only **defined + `filterable`** field keys are queryable (prevents arbitrary JSON path injection); operator allowlist; `page_size` cap; typed-value coercion via the field definition before binding.

**Performance (§16):** Postgres GIN index on `data` (`jsonb_path_ops`); optionally expression indexes on hot fields later. SQLite path is functional-only (tests), not perf-tuned. This engine is designed **now** so record storage and API shape support it — implemented in 4.2, not bolted on later.

## 12. Audit history

Reuse `AuditService.log_event` with `resource_type="custom_object_record"`, `resource_id=<record id>`, `action_metadata={object_key, changed_fields}` on create/update/delete. Object-definition changes audited too. (Full field-level diff timeline is a possible 4.2b enhancement.)

## 13. Soft deletion

`BaseModel.is_deleted/deleted_at` on both new tables. Record DELETE = soft; list queries filter `is_deleted == False`. Deleting an **object definition** soft-deletes it and (proposed) blocks/warns if it has live records or inbound references — decision for review: cascade-soft-delete records vs. block.

## 14. Import / export

Reuse `services/import_/` (parsers + `header_mapper` + `validation_engine` + `template_generator`). Map incoming columns → object field keys; validate each row via `MetadataValidationEngine`; bulk-insert records. Export = records `data` flattened by field defs (respecting `exportable`). No new import framework.

## 15. Industry independence

Custom Objects are **pure per-tenant configuration**. Property/Policy/Loan/Case become object definitions created by (or seeded for) a tenant — **never Core code, never industry modules in Core**. Extend `test_architecture_boundary.py`: the object engine (`custom_object_*` models/services, records API, query engine) imports **no** industry module; `SUPPORTED` core entity set stays `{lead, contact}` while object keys are per-tenant data. This preserves the Phase 3.1 / 4.1 boundary.

## 16. Migration strategy & performance

- **Migration (this IS a migration, unlike 4.1):** one additive, reversible Alembic revision creating `custom_object_definitions` + `custom_object_records` (+ FKs, + indexes on `organization_id`, `object_definition_id`). **Non-destructive**; Lead/Contact/existing `custom_field_definitions` untouched. Must be idempotent + SQLite-and-Postgres safe (follow the Phase 3 `7b9a4002721f` inspector-guarded pattern; use `sa.JSON` which maps to JSONB on PG).
- **`entity_type` extension needs no DDL** (already a string).
- **Performance:** Postgres GIN index on `custom_object_records.data`; composite index `(organization_id, object_definition_id, is_deleted)`; `page_size` caps; queries restricted to defined filterable fields. Watch: unindexed JSON scans at scale → document GIN + optional per-field expression indexes as a follow-up.
- **Prod reality:** prod has no alembic-on-deploy + `RUN_CREATE_ALL=true` (per ops notes), so `create_all` will materialize the new tables on deploy, but the alembic revision must still exist for correctness and for environments that migrate. Flag: verify the new tables land on the real VPS (the known alembic-not-run gap).

---

## Required refactors (small, in existing files)

1. `core/reserved_fields.py`: `is_supported_entity_type` becomes org-aware (core set ∪ active object keys) — or the object-key check moves into `CustomFieldService` as an async lookup. Base reserved keys for records: `id, organization_id, created_at, updated_at, is_deleted, created_by, updated_by`.
2. `CustomFieldService._validate_definition_input`: allow an object-key `entity_type` when a matching active object def exists (async check).
3. `api/v1/metadata.py` `bootstrap`: include `custom_objects`; keep field defs lazy per object (avoid payload bloat).

## Risks

| Risk | Mitigation |
|---|---|
| `entity_type` collision (object key == "lead"/other object) | Enforce uniqueness + reserved-name check at object create |
| JSON query perf at scale | GIN index; filterable-only fields; page caps; defer expression indexes |
| Cross-DB cast differences (SQLite vs PG) | Central `build_record_filter` helper keyed off field types; test both |
| Bootstrap bloat if all object fields eager-loaded | Lazy per-object field loading |
| Object/record delete orphaning references | Decide cascade-soft-delete vs block-on-references (review item) |
| Prod alembic-not-run gap | Rely on `RUN_CREATE_ALL` but ship the revision; verify tables on VPS |

## Explicit non-goals (Phase 4.2)

Seeded industry objects (Property/Policy/Loan as shipped config); workflow/automation triggers on object records; AI over records; advanced M2M relationship graph with attributes (unless approved); computed/rollup fields; per-record field-level permissions; mobile record UI; full report-builder integration for objects.

---

## Decisions for your review (before implementation)

1. **Relationships scope:** single + multi `entity_reference` now, defer the typed relationship join-table? *(Recommended: yes, defer the join-table graph.)*
2. **Object-definition delete:** cascade-soft-delete its records, or block while records/references exist? *(Recommended: block with a clear error; offer explicit "delete with records".)*
3. **Query engine breadth:** ship the 10-operator set above in 4.2, or start with `eq/gt/gte/lt/lte/contains`? *(Recommended: full set — the cast helper is the hard part either way.)*
4. **Bootstrap:** object definitions eager, field defs lazy per object? *(Recommended: yes.)*

---

**STOP.** Per the plan-first workflow, implementation halts here pending review. No production code, schemas, migrations, or tests were modified in this step.
