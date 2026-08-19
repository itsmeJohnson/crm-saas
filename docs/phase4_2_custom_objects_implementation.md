# Phase 4.2 — Custom Objects · Implementation Report

**Date:** 2026-08-20
**Approach:** Built on the Phase 4.1 Custom Fields Engine — objects reuse `CustomFieldDefinition`, `MetadataValidationEngine`, and `DynamicCustomFields`. No competing metadata system.
**Approved decisions honored:** single + multi `entity_reference` (join-table graph deferred) · delete blocked while records exist (no cascade) · full 10-operator query engine · bootstrap eager objects / lazy fields.

---

## Architecture delivered

```
Custom Object Definition (custom_object_definitions)
      │  key ── attaches fields via CustomFieldDefinition.entity_type == key
      ├── Fields  → CustomFieldDefinition (existing table, reused)
      └── Records → custom_object_records.data (JSON/JSONB)
                     ├── validation  → MetadataValidationEngine (reused)
                     ├── filtering   → core/record_query.py (typed, 10 ops)
                     ├── sorting     → core/record_query.py
                     ├── pagination  → CustomObjectRecordService
                     └── relationships → entity_reference (single + multi)
```

CRM Core stays industry-independent: objects are pure per-tenant config; the object engine imports no industry module (guarded by `test_architecture_boundary.py`).

## Files created

**Backend**
- `app/models/custom_object.py` — `CustomObjectDefinition`, `CustomObjectRecord` (shared JSON record table, `BaseModel` soft-delete, composite index).
- `app/core/record_query.py` — central typed filter/sort engine: 10 operators, per-type operator allowlist, one SQLite/PostgreSQL abstraction (explicit text cast + numeric `Float` cast), filterable-only guardrail.
- `app/services/custom_object_service.py` — object definition CRUD; reserved/duplicate key guards; **delete blocked while records exist (409)**.
- `app/services/custom_object_record_service.py` — record CRUD + validate (via engine) + typed list/filter/sort/paginate.
- `app/schemas/custom_object.py` — object + record + record-list schemas.
- `app/api/v1/custom_objects.py` — `/objects` + `/objects/{key}/records` generic router.
- `alembic/versions/c1d2e3f4a5b6_add_custom_objects.py` — additive, reversible, inspector-guarded migration.
- `app/tests/test_custom_objects.py` — 16 tests (see coverage below).

**Frontend**
- `src/services/objectApi.ts` — object + record client (typed filters/sort/paginate).
- `src/components/objects/RecordFormModal.tsx` — record create/edit via shared `DynamicCustomFields`.
- `src/pages/CustomObjectsPage.tsx` — object manager: create objects, per-object field builder, record table with add/edit/delete.
- Tests: `RecordFormModal.test.tsx`, `CustomObjectsPage.test.tsx`.

## Files modified

- `app/core/custom_field_types.py` — added `entity_reference` type + `REFERENCE_TYPES`/`LIST_TYPES`.
- `app/core/reserved_fields.py` — dynamic entity support (core ∪ active object keys); `_RECORD_RESERVED` (records reserve only system columns, so `name` etc. are valid object field keys); `RESERVED_OBJECT_KEYS` + `is_reserved_object_key`.
- `app/services/custom_field_service.py` — `entity_type` may be an active custom-object key (async allowlist check).
- `app/services/metadata_validation_engine.py` — `entity_reference` validation (shape + tenant-scoped existence); parameterized `json_field` + `extra_unique_filters` so records reuse the engine over the `data` column.
- `app/api/v1/metadata.py` — `bootstrap` returns `custom_objects` (eager).
- `main.py` — registered `/objects` router.
- `app/models/__init__.py` — registered the two models.
- `app/tests/test_architecture_boundary.py` — guards extended to the object engine.
- Frontend `metadataApi.ts`, `metadataStore.ts`, `moduleRegistry.ts` — bootstrap `custom_objects`, store `customObjects`, `/custom-objects` route.

## API

```
GET/POST            /api/v1/objects
GET  /api/v1/objects/{key}      PATCH/DELETE /api/v1/objects/{id}
GET  /api/v1/objects/{key}/records?filters=<json>&sort=field:desc&page=&page_size=
POST /api/v1/objects/{key}/records
GET/PATCH/DELETE    /api/v1/objects/{key}/records/{id}
# object fields reuse the existing endpoint:
GET/POST /api/v1/metadata/custom-fields?entity_type=<object_key>
```

## Query engine — 10 operators, typed, cross-DB

`eq, ne, gt, gte, lt, lte, contains, startswith, in, is_empty`. Each filter is validated against the field's declared type and a per-type operator allowlist; invalid field/operator/type → 400 (never silent wrong results). Numeric fields compared with a SQL `Float` cast; dates as ISO strings (lexicographic); booleans via explicit text cast (fixes SQLite int/text affinity); multiselect + multi-reference via JSON-array membership. Only **active + filterable** fields are queryable/sortable.

## Safety (verified by tests)

Tenant A cannot see B's objects, query B's records, reference B's records, modify B's definitions, or fetch B's record ids (all → 404/400). Deleting an object with live records → **409**. Cross-tenant `entity_reference` → **400**.

## Test coverage (`test_custom_objects.py`, 16)

object CRUD · reserved/duplicate object keys · non-admin blocked · **delete-protection (409)** · fields attach to objects · field on unknown object rejected · record CRUD + all field types · record validation · `entity_reference` single+multi + dangling rejected · **cross-tenant reference rejected** · tenant isolation (objects+records) · 10 query operators + typed filtering + sort + pagination · invalid filters (unknown field/op, type mismatch, bad value) · HTTP API flow (+bootstrap) · non-admin API 403 · **Lead/Contact backward compatibility**.

## Migration

`c1d2e3f4a5b6` (additive, reversible). Single alembic head. **Verified on SQLite**: upgrade → idempotent re-run → downgrade round-trip creates/drops both tables with the unique constraint + composite index. Uses `sa.JSON` (portable; JSON on PG, JSON1 on SQLite).

## Test results

| Suite | Phase 4.1 baseline | Phase 4.2 final | Delta |
|---|---|---|---|
| Frontend `vitest` | 257 passed | **261 passed / 0 failed** (94 files) | +4 object tests; 0 new failures (2 known dashboard-widget flakes are non-deterministic, pass in isolation) |
| `tsc --noEmit` | PASS | **PASS** | — |
| `npm run build` | PASS | **PASS** (`✓ built in ~13s`) | — |
| Backend `pytest` | 1046 passed / 8 pre-existing failed / 13 skipped | **1056 passed / 14 failed / 13 skipped** | +object tests green; **0 failures caused by Phase 4.2** |

### Backend failure analysis (14 = 8 pre-existing + 6 date-rollover, none from Phase 4.2)

- **8 pre-existing infra failures** (identical to the Phase 4.1 baseline): redis lock, feature-guard cache, cache invalidation, lifespan-shutdown ×2, scheduled-reports mocks, trial-requests ×2.
- **6 date-boundary flakes** surfaced because the ~35-min run crossed midnight into 2026-08-20: `test_dashboard::test_dashboard_summary_extended_widgets` (asserts a lead created "today" appears in the today bucket → 0), `test_employee_dashboard::test_employee_summary_scoped_to_self`, and `test_historical_analytics_module` ×4 (metric-snapshot date-window / CSV export).
- **Proof these are NOT from Phase 4.2:** with **all** Phase 4.1+4.2 changes stashed (tree reverted to the last commit), the same tests **still fail** — they are environmental date flakes, matching the project's known tz/date-boundary flake pattern. Custom-object tests (`test_custom_objects.py` 16/16) and the Phase 4.1 suite (54/54) pass.

## Known issues / notes

- Boolean/date JSON querying relies on text-cast + ISO ordering — correct on SQLite and PG; documented.
- `entity_reference` multi + `contains` uses JSON-array LIKE membership (pragmatic, cross-DB) — exact array semantics (order/dedup) are not enforced at query time.
- Redis-dependent backend tests remain pre-existing failures locally.

## PostgreSQL verification (done locally against real PG 18.3)

Verified against a **real PostgreSQL 18.3** instance (not just SQLite):

- **Migration DDL round-trip:** `c1d2e3f4a5b6` upgrade creates both tables with correct PG types (`id` UUID, `organization_id` UUID, `data` JSON, `created_at` TIMESTAMP, `is_deleted` BOOLEAN), the `uq_custom_object_org_key` unique constraint, and all three indexes incl. the composite `ix_custom_object_records_org_obj_deleted`. Idempotent re-run OK. Downgrade drops both cleanly.
- **`create_all` on Postgres (mirrors prod `RUN_CREATE_ALL`):** the full `Base.metadata.create_all` builds the entire schema — including the two new tables — on Postgres with no errors.
- **Services + query engine on Postgres:** ran the real service stack (object + field + record creation, validation) and the typed query engine end-to-end on PG. Results correct: `value>=8M`→2, `Commercial AND value>=10M`→1, `active=true`→2 (confirms the cross-DB boolean text-cast works on PG's `true`/`false`), `sort value:desc`→`[20M, 8M, 5M]`. The SQLite/PostgreSQL abstraction is proven on both engines.

## ⚠️ Remaining production gate (needs your infra — I cannot reach prod)

The **actual VPS production database** steps are yours to run (runbook below). Local PG proves the migration + query engine are Postgres-correct; it does not prove the apply against live prod data.

**Index guidance (corrected):** the earlier "GIN index" note is **not** the right tool for this query pattern. Filters use `->>` scalar extraction with range/equality, which GIN (`jsonb_path_ops`, for `@>` containment) does not accelerate. The right optimizations at load are (a) switch `data` to **JSONB** on PG via `JSON().with_variant(JSONB, "postgresql")` (keeps SQLite portable) and (b) add **B-tree expression indexes** on hot fields, e.g. `CREATE INDEX ON custom_object_records (organization_id, object_definition_id, ((data->>'value')::numeric))`. The composite btree index already created covers the common org+object scoping. Treat these as post-launch tuning, added per hot field.

## Deferred (Phase 4.2b / later)

Typed relationship join-table graph (M2M with attributes, cascade rules); computed/rollup fields; per-record field-level permissions; object import/export UI (backend import framework is reusable); GIN/expression indexes; report-builder integration for objects.
