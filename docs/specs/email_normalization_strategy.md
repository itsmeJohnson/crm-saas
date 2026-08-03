# Centralized Email Normalization Strategy

**Sprint:** Launch Sprint 0 (follow-up to M2)
**Status:** Specification — awaiting approval (NO CODE WRITTEN)
**Author:** Claude
**Date:** 2026-08-03

> Goal: exactly one place decides what a stored user email looks like, and every
> runtime path — login, signup, invitation, admin-create-user, replace-employee,
> update-user, password-reset — inherits it automatically. No scattered `.lower()`.

---

## 1. Problem recap

The M2 fix normalized only self-serve signup ([auth_service.py:58](../../backend/app/services/auth_service.py#L58))
and one lookup ([repositories/user.py:11](../../backend/app/repositories/user.py#L11)). Five other write
paths still store mixed-case emails, and their dedup checks are case-sensitive
(see the prior audit): invite + accept, admin create-user, replace-employee,
update-user. Two separate `UserRepository` classes and per-call `func.lower()` /
`.strip().lower()` make this a whack-a-mole problem. We need a single choke point.

---

## 2. Design: normalize at the ORM column boundary

Two artifacts, one behavior:

### 2.1 The single source of truth (pure function)
`app/core/email_utils.py` (new):
```
normalize_email(raw: str | None) -> str | None
    None            -> None
    otherwise       -> unicodedata.normalize("NFC", raw), .strip(), .casefold()/.lower()
    empty after strip -> None
```
Rules (deliberately minimal):
- **Trim** surrounding whitespace.
- **Lowercase** the whole address (see §7 for the RFC local-part nuance and why).
- **Unicode NFC** normalize so visually identical addresses compare equal.
- **Do NOT** strip `+tags`, dots, or subaddressing — that would merge distinct
  real mailboxes and is a security/correctness hazard.
- **Idempotent**: `normalize_email(normalize_email(x)) == normalize_email(x)`.

This is the ONLY function that encodes the rules. Nothing else calls `.lower()`
on an email.

### 2.2 The enforcement point (SQLAlchemy TypeDecorator)
`app/models/types.py` (new):
```
class NormalizedEmail(TypeDecorator):
    impl = String
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return normalize_email(value)
```
Apply it to the identity columns:
- `User.email`  → `mapped_column(NormalizedEmail(255), unique=True, index=True, nullable=False)`
- `UserInvitation.email` → `mapped_column(NormalizedEmail(255), nullable=False, index=True)`

**Why a TypeDecorator (not `@validates`, not a service helper):**
`process_bind_param` runs for **both** directions through one implementation:
1. **Writes** — every ORM insert/update flushes the value through it, regardless of
   which repository or service issued it. `BaseRepository.create` does
   `self.model(**data)` and `BaseRepository.update` does `setattr` → both flush
   through the column type. So admin-create, invite-accept, replace-employee, and
   update-user are all covered **without touching those services**.
2. **Comparisons** — `User.email == x` binds `x` through the same
   `process_bind_param`, so `get_by_email`, `get_by_email_global`,
   `get_user_by_email`, and the reset query all become case-insensitive **for free**,
   because the stored side is guaranteed normalized and the query side is normalized
   identically. This is the property `@validates` cannot give (it only guards writes).

The underlying DB type stays `VARCHAR(255)` — the decorator is Python-side, so **no
column-type DDL** is required (only a data backfill, §5).

---

## 3. What this removes (de-duplication)

Once the decorator is in place, the scattered M2 logic becomes redundant and MUST
be reverted so there is a single source of truth:

| Location | Current (M2) | After |
|----------|--------------|-------|
| [auth_service.py:58](../../backend/app/services/auth_service.py#L58) | `request.admin_email.strip().lower()` | `request.admin_email` (decorator normalizes) |
| [repositories/user.py:11](../../backend/app/repositories/user.py#L11) | `func.lower(email) == …strip().lower()` + `func` import | `self.model.email == email` |
| [api/v1/auth.py forgot_password](../../backend/app/api/v1/auth.py#L246) | `func.lower(User.email) == payload.email.strip().lower()` + `func` import | `User.email == payload.email` |

No other service (`user_service`, `invitation_service`) needs email-specific code —
they keep passing the raw request value and the column normalizes it.

---

## 4. Preserving display / original casing

"Display name" for a person is already modeled separately (`first_name`,
`last_name`) and is untouched. The remaining question is whether to preserve the
user's *typed email casing* (e.g. show `John.Doe@Acme.com` while authing on
`john.doe@acme.com`).

**Recommendation: do NOT add a display-email column now.** The canonical lowercase
address is the industry-standard thing to display, and a second column is one more
thing to keep in sync. Ship with the single normalized `email`.

**If product later needs it** (spec'd here so it's a known, clean extension):
- Add `email_display: Mapped[str | None]` (plain `String(255)`, NOT the decorator).
- Populate it with the raw input **at the service boundary only** (create/update),
  never used for auth, lookup, or uniqueness.
- Emails/UI may render `email_display or email`.
This keeps the canonical/identity value and the cosmetic value cleanly separated.

---

## 5. Database migration

**Revision:** `email_normalize_0001`, `down_revision = reset_token_tz_0001`.

No type change. Two steps, guarded:

**Step A — collision pre-flight (fail loud, never lose data).**
Before backfilling, detect rows that would collapse to the same canonical value and
violate the unique index:
```sql
SELECT lower(btrim(email)) AS canon, count(*), array_agg(id)
FROM users GROUP BY 1 HAVING count(*) > 1;
```
If any rows return, the migration **raises with the offending list** and does not
proceed. Case-variant duplicates are a data problem requiring a human decision
(merge / deactivate); document the remediation runbook. (These duplicates are
exactly what the current gap allowed to exist.)

**Step B — backfill (idempotent).**
```sql
UPDATE users            SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));
UPDATE user_invitations SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));
```
For `user_invitations`, pending case-duplicate invites can simply be de-duplicated
(keep newest) rather than blocking.

**Step C (recommended hardening, optional) — functional unique index.**
```sql
CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));
```
Belt-and-suspenders: even if a future code path ever bypasses the ORM (raw SQL),
the DB refuses a case-duplicate. With the decorator guaranteeing normalized writes,
the existing plain unique index already suffices, so this is optional.

`downgrade()` is a no-op (lowercasing is not reversibly "un-normalizable"; leaving
values lowercased is harmless).

---

## 6. Coverage matrix — every required flow through one implementation

| Flow | Entry | Mechanism |
|------|-------|-----------|
| **Signup** | `register_tenant` → `user_repo.create` | write → decorator |
| **Login** | `authenticate_user` → `get_by_email` | compare → decorator |
| **Invitation (create)** | `invite_user` → `UserInvitation` insert + `existing_pending_invite` | write + compare → decorator |
| **Invitation (accept)** | `accept` → `create_user` | write → decorator |
| **Admin create user** | `POST /users` → `user_service.create_user` → `create_user` + `get_by_email_global` | write + compare → decorator |
| **Replace employee** | `user_service.replace_employee` → `create_user` + `get_by_email_global` | write + compare → decorator |
| **Update user** | `PATCH /users/{id}` → `update_user` → base `setattr` | write → decorator |
| **Password reset** | `forgot_password` / `reset_password` queries | compare → decorator |

Every row resolves to the same `NormalizedEmail` column type calling the same
`normalize_email`.

---

## 7. Risks & edge cases

| Risk | Note / mitigation |
|------|-------------------|
| **Existing case-duplicate rows** | Migration Step A fails loud with the list; resolve manually before deploy. |
| **RFC local-part case-sensitivity** | Per RFC 5321 the local part *may* be case-sensitive; in practice ~all providers treat it case-insensitively. We lowercase fully for consistent dedup, predictable login, and user expectation. Accepted trade-off; documented. |
| **Raw SQL bypass** | `process_bind_param` only covers ORM/Core statements. Any `text("… email = :e")` query would bypass it. **Audit item:** grep for raw SQL touching `email` (current reset/login/user paths are all ORM — clean). The optional functional index (§5C) neutralizes this permanently. |
| **Over-normalization** | Explicitly not stripping `+tags`/dots avoids merging distinct mailboxes. |
| **Other email columns** | `Organization.support_email` / `billing_email` are contact/display fields, not identity — intentionally **out of scope**, left as plain `String`. |
| **`casefold()` vs `.lower()`** | Prefer `.lower()` after NFC for ASCII-domain predictability; `casefold()` can over-fold some scripts. Spec uses `.lower()`. |

---

## 8. Testing strategy

**Unit — `normalize_email`:** trim, lowercase, NFC, `None`→`None`, whitespace-only→`None`,
idempotency, and negative cases (does NOT strip `+tag`/dots).

**Unit — `NormalizedEmail` decorator:** inserting `Mixed@X.com` stores `mixed@x.com`;
`select(User).where(User.email == "MIXED@x.COM")` finds it.

**Integration — parametrized over all 7 flows + reset:** each write persists a
normalized email; each lookup resolves regardless of input case.

**De-duplication:** creating a case-variant across two different paths (e.g. signup
then admin-create) is rejected by uniqueness; `forgot_password` returns a single row
(no `MultipleResultsFound`) because duplicates can no longer exist.

**Regression:** existing `test_password_reset_sprint0.py`, auth, user, invitation
suites stay green after the M2 reverts.

**Migration:** seed mixed-case rows → backfill lowercases them; seed a deliberate
collision → Step A raises with the offending IDs.

---

## 9. Files affected

| File | Change | Type |
|------|--------|------|
| `app/core/email_utils.py` | `normalize_email` — single source of truth | **new** |
| `app/models/types.py` | `NormalizedEmail` TypeDecorator | **new** |
| `app/models/user.py` | `email` column → `NormalizedEmail(255)` | edit |
| `app/models/invitation.py` | `email` column → `NormalizedEmail(255)` | edit |
| `app/services/auth_service.py` | revert M2 `.strip().lower()` | edit |
| `app/repositories/user.py` | revert M2 `func.lower(...)`; drop `func` import | edit |
| `app/api/v1/auth.py` | revert M2 `func.lower(...)`; drop `func` import if unused | edit |
| `alembic/versions/email_normalize_0001_*.py` | collision pre-flight + backfill (+ optional index) | **new** |
| `app/tests/test_email_normalization.py` | unit + decorator + flow + migration tests | **new** |
| `docs/DECISIONS.md` | ADR for the strategy (on completion) | edit |

---

## 10. Acceptance criteria

- [ ] `normalize_email` is the only function that lowercases/trims an email; no other
      runtime `.lower()`/`func.lower()` on emails remains (M2 reverts done).
- [ ] `User.email` and `UserInvitation.email` use `NormalizedEmail`; all 8 flows in §6
      persist and look up normalized values with no per-service email code.
- [ ] A case-variant address cannot create a second account via any path.
- [ ] `forgot_password` cannot raise `MultipleResultsFound`.
- [ ] Migration backfills existing rows and fails loudly on pre-existing collisions.
- [ ] All new + existing auth/user/invitation/reset tests pass.

---

**Do not implement until approved. Implement as one unit (decorator + reverts +
migration must land together to avoid a mixed state).**
