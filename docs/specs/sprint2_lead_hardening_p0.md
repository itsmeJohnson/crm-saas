# Sprint 2 — Lead Management Hardening (P0) — Implementation Specification

**Status:** Specification — awaiting approval (NO CODE WRITTEN)
**Author:** Claude
**Date:** 2026-08-03
**Scope:** Close the write-side multi-tenancy gaps from the Lead audit (B1, B2).
Validation only — **no redesign, no new features, no API changes, no frontend
behavior changes.**

---

## 0. Shared design (applies to issues 1–4)

Issues 1–4 are the same class of bug (unvalidated foreign keys) with an identical
fix, so they share one helper rather than four copy-pasted blocks.

**New private helper on `LeadService`:**
```
async def _validate_org_references(self, actor, data: dict) -> None
    # For each of stage_id / branch_id / territory_id / company_id that is
    # PRESENT and non-None in `data`, assert a row exists with that id,
    # organization_id == actor.organization_id, is_deleted == False.
    # Raise HTTP 400 with a field-specific message otherwise.
    # Absent or None keys are skipped (nullable FKs stay backward-compatible).
```
Each referenced table (`pipeline_stages`, `branches`, `territories`, `companies`)
extends `BaseModel` → already has `organization_id` (indexed) and `is_deleted`, so
each check is one indexed point lookup. The helper is called from **`create_lead`**
and **`update_lead`**.

Issue 5 (bulk `assigned_user_id`) reuses the existing authoritative
`UserService.get_assignable_user_ids(actor)` — which already encodes *org +
active + assignable-scope* — so we do not re-derive that logic.

---

## Issue 1–4: Validate stage_id / branch_id / territory_id / company_id belong to the org

### 1. Current implementation
- `create_lead` ([lead_service.py:45](../../backend/app/services/lead_service.py#L45)) validates only `assigned_user_id`'s org+active. It auto-links `company_id` and auto-resolves `branch_id`/`territory_id` from PIN/city (both org-scoped, safe), but a **client-supplied** `stage_id`, `branch_id`, `territory_id`, or `company_id` is passed straight through.
- The repo `create_lead` ([lead_repository.py:17](../../backend/app/repositories/lead_repository.py#L17)) only picks a default stage when `stage_id` is absent — a provided one is used as-is, unvalidated.
- `update_lead` ([lead_service.py:318](../../backend/app/services/lead_service.py#L318)) validates only `assigned_user_id`; `stage_id`/`branch_id`/`territory_id`/`company_id` go straight to `repo.update_lead` → `setattr`.

### 2. Root cause
Only `assigned_user_id` had an org-membership guard. The other four FK columns were added later (company auto-link, branch/territory) with no equivalent guard on the **explicit-input** path. The DB FK constraint only requires the id to exist *in some org*, so a valid **other-org** id is accepted.

### 3. Proposed solution
Add `_validate_org_references(actor, data)` (see §0) and call it:
- In `create_lead`: **before** `repo.create_lead(...)`, validating the incoming `lead_data` (the auto-link/auto-resolve steps only fill *absent* keys with org-correct values, so they need no re-validation; validating the caller's explicit values is sufficient).
- In `update_lead`: **after** the `get_lead` scoping check, **before** `repo.update_lead(...)`.

On failure: `HTTP 400` — e.g. `"stage_id not found in your organization"`.

### 4. Files to modify
| File | Change |
|------|--------|
| `backend/app/services/lead_service.py` | Add `_validate_org_references`; call in `create_lead` + `update_lead` |

No repository, model, schema, router, or frontend change.

### 5. Database impact
**None.** No schema/migration. Adds ≤4 indexed point lookups per create/update (org_id + pk) — negligible.

### 6. Backward compatibility
- Leads with valid same-org refs: unaffected.
- Frontend already populates these fields from **org-scoped pickers**, so its requests pass unchanged → no frontend behavior change.
- Only requests carrying **cross-org / non-existent / soft-deleted** ids now get 400 — which is exactly the vulnerability being closed.
- **Partial updates unaffected:** `update_lead` validates a FK only when its key is present in the PATCH body, so a PATCH that doesn't touch `stage_id` never re-validates it (important for leads sitting on a since-soft-deleted stage).

### 7. Edge cases
- Key absent / value `None` → skipped (nullable FK preserved).
- Ref points to a **soft-deleted** row in the same org → rejected (`is_deleted == False` required).
- `company_id` supplied explicitly by client → now validated (previously only the auto-link path was org-safe).
- Auto-resolved `branch_id`/`territory_id` (from PIN) → org-derived, not re-validated (safe by construction).

### 8. Tests to write
- create: cross-org `stage_id`/`branch_id`/`territory_id`/`company_id` → 400 (one test each).
- create: valid same-org `stage_id` → 201; no FK fields (defaults) → 201.
- update: cross-org `stage_id` → 400; valid same-org → 200.
- update: PATCH not touching FKs → 200 (no false rejection).
- Cross-tenant proof: Org-A actor sending Org-B `stage_id` → 400, and Org-A lead's `stage` in the response never reflects Org-B data.

### 9. Complexity
**Low.** One ~15-line helper + two call sites.

### 10. Risks
- Over-strict rejection of a legitimate flow — **low** (frontend uses org-scoped ids). Mitigated by the "skip when absent/None" rule and by validating only explicit inputs.
- Perf — negligible (indexed lookups).

---

## Issue 5: Validate assigned_user_id during bulk updates (org + active + assignable)

### 1. Current implementation
`bulk_update` ([lead_service.py:270](../../backend/app/services/lead_service.py#L270)) validates a supplied `stage_id` against the org, then blindly `setattr(lead, key, val)` for every field — including `assigned_user_id` — with **no** user validation ([:300](../../backend/app/services/lead_service.py#L300)). `LeadBulkUpdateFields.assigned_user_id` is an optional UUID with no server-side membership check.

### 2. Root cause
Bulk update was built as a generic allow-listed field setter; `assigned_user_id` is in the allow-list but skipped the org/active/assignable guard that single create/update applies for the assignee.

### 3. Proposed solution
In `bulk_update`, when `fields` contains a non-None `assigned_user_id`, validate it is within `await UserService(self.db).get_assignable_user_ids(actor)` (org + active + assignable-scope, single source of truth). If not → `HTTP 400` (`"Assigned user is not valid/assignable in your organization"`). Reject the whole request (consistent with the existing `stage_id` behavior in the same method) rather than silently skipping — an invalid assignee is a client error, not a partial-success case.

### 4. Files to modify
| File | Change |
|------|--------|
| `backend/app/services/lead_service.py` | Add assignee validation in `bulk_update` (reuse `get_assignable_user_ids`) |

No schema/API/frontend change. (`get_assignable_user_ids` already exists and is used by the transfer + bulk-assign pickers, so the frontend already only offers valid options.)

### 5. Database impact
**None.** One extra scoped query (already the same query the picker uses).

### 6. Backward compatibility
- Bulk updates that reassign to a valid assignable user: unchanged.
- The frontend bulk-assign picker is already populated from `get_assignable_user_ids`, so legitimate UI requests pass unchanged.
- Only cross-org / inactive / non-assignable target ids now 400 — the bug being closed.

### 7. Edge cases
- `assigned_user_id` absent from `fields` → skipped (bulk without reassignment still works).
- Target == actor → allowed (present in own assignable set).
- Team-leader bulk-assigning to a **peer** (not in downline) → now correctly rejected.
- Inactive / soft-deleted target → rejected.
- Combined with an invalid `stage_id` → existing stage check fires first; either 400s.

### 8. Tests to write
- bulk `assigned_user_id` from another org → 400.
- bulk `assigned_user_id` inactive user → 400.
- bulk `assigned_user_id` a non-assignable peer (TL actor) → 400.
- bulk `assigned_user_id` a valid assignable user → updates succeed (count correct).
- bulk without `assigned_user_id` (e.g. status change) → unchanged behavior.

### 9. Complexity
**Low.** ~5 lines reusing an existing helper.

### 10. Risks
- Changing bulk semantics to hard-400 on a bad assignee (previously would have applied it) — **intended**; the previous behavior was the vulnerability. Low risk.

---

## Cross-cutting

- **Do NOT touch** single-lead `assigned_user_id` validation (already org+active) — out of scope; changing it to "assignable" would alter existing behavior. Noted, not changed.
- **APIs unchanged**: same routes, same request/response shapes; only new 400s for invalid cross-org input.
- **Frontend unchanged**: pickers already emit org-scoped ids.

## Post-approval plan (per your instructions)
1. Implement the helper + 3 call sites.
2. Unit + integration tests (new file `backend/app/tests/test_lead_org_fk_hardening.py`).
3. Run the Lead Management suite (`test_lead_*`, `test_crm_*`, `test_pipeline_*`).
4. Regression: auth (`test_auth*`, `test_password_reset_sprint0`) + trial onboarding (`test_super_admin*`, invitation).
5. Self-review vs the checklist (cross-tenant leakage, IDOR, org boundaries, CRUD/trial/auth regressions) + production-readiness assessment.
6. **No commit, no push.** Wait for approval.

---

**Do not implement until approved.**
