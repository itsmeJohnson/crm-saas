# H2 — Encrypt MFA Secret at Rest (ADR-002)

**Sprint:** 1 — Authentication Hardening
**ADR:** ADR-002
**Status:** Specification — awaiting approval (NO CODE WRITTEN)
**Author:** Claude
**Date:** 2026-08-03

> Scope note: This spec covers **only** the TOTP `mfa_secret` field. Account
> lockout (ADR-003 / H3) is out of scope and will be specified separately.
> One issue at a time.

---

## 1. Current Implementation

TOTP secrets are stored **in plaintext**.

**Model** — `backend/app/models/user.py:42`
```python
mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
```
The value is a raw base32 string produced by `pyotp.random_base32()` (32 chars).

**Service** — `backend/app/services/mfa_service.py`
The secret is written and read as plaintext in five places:

| Line | Operation | Access |
|------|-----------|--------|
| `generate_setup` (~80) | `user.mfa_secret = secret` | **write** plaintext |
| `enable_mfa` (~106) | `pyotp.TOTP(user.mfa_secret)` | **read** plaintext |
| `disable_mfa` (~137) | `pyotp.TOTP(user.mfa_secret)` | **read** plaintext |
| `verify_totp` (~165) | `pyotp.TOTP(user.mfa_secret)` | **read** plaintext |
| `regenerate_backup_codes` (~206) | `pyotp.TOTP(user.mfa_secret)` | **read** plaintext |

**Consequence:** anyone with read access to the database (dump, backup, SQL
injection, insider) can reconstruct any user's TOTP generator and defeat MFA
entirely. This is the exact class of risk H1 closed for refresh tokens.

**Important asymmetry vs. H1:** refresh tokens were *hashed* (one-way) because the
server only ever needs to compare. The MFA secret must be **recoverable** to
generate/verify TOTP codes, so hashing is not an option — we need **reversible
encryption**.

**Current state of dependencies/config:**
- `cryptography` is **not** in `requirements.txt` (only `pyotp>=2.9.0`).
- No `APP_ENCRYPTION_KEY` exists in `backend/app/core/config.py`.
- Backup codes are already SHA-256 hashed (`mfa_backup_codes`) — **not affected** by this change.

---

## 2. Proposed Solution

Encrypt `mfa_secret` at rest using **Fernet** (AES-128-CBC + HMAC-SHA256,
authenticated symmetric encryption) from the `cryptography` package, keyed by a
new `APP_ENCRYPTION_KEY` setting — exactly as named in ADR-002.

### 2.1 Encryption helper (new module)
Create `backend/app/core/crypto.py`:

```
VERSION_PREFIX = "enc:v1:"

encrypt_secret(plaintext: str) -> str
    # returns  "enc:v1:" + Fernet(key).encrypt(plaintext)

decrypt_secret(stored: str | None) -> str | None
    # if None            -> None
    # if starts "enc:v1:" -> Fernet(key).decrypt(...)   (strip prefix)
    # else                -> return stored unchanged      (LEGACY plaintext)
```

The `enc:v1:` version prefix does three jobs:
1. **Backward compatibility** — legacy plaintext rows (no prefix) are detected
   and returned as-is, so decryption works before *and* after the data migration.
2. **Idempotent migration** — the migration only encrypts rows that lack the prefix.
3. **Future key rotation** — a later `v2` can be introduced without ambiguity
   (via `MultiFernet`), no schema change needed.

### 2.2 Service integration (explicit, at the service boundary)
Mirror H1's philosophy: keep the model a plain column, encrypt/decrypt at the
service layer. Concretely, in `mfa_service.py`:

- **Write** (`generate_setup`): `user.mfa_secret = encrypt_secret(secret)`
- **Read** (all four `pyotp.TOTP(...)` call sites): introduce a single private
  helper `_load_secret(user) -> str | None` that returns
  `decrypt_secret(user.mfa_secret)`, and build the TOTP from that. This keeps
  decryption in exactly one place (DRY) and guarantees no read site is missed.

> Alternative considered: a SQLAlchemy `TypeDecorator` (`EncryptedString`) for
> fully transparent encrypt/decrypt at the ORM layer. Rejected as the *primary*
> approach for parity with H1 (which kept crypto explicit at the boundary),
> easier unit testing, and no surprising ORM-load behavior. Can be revisited if
> more fields need encryption later.

### 2.3 Key management
Add to `config.py`:
```python
# Encryption (ADR-002) — Fernet key, url-safe base64, 32 bytes
APP_ENCRYPTION_KEY: str = "<dev-only default>"
```
- Extend the existing `validate_production_config` validator so a default/empty
  `APP_ENCRYPTION_KEY` **raises in production** (same guard pattern already used
  for `JWT_SECRET_KEY`).
- Document generation: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

---

## 3. Files Affected

| File | Change | Type |
|------|--------|------|
| `backend/requirements.txt` | Add `cryptography>=42.0.0` | edit |
| `backend/app/core/crypto.py` | Fernet encrypt/decrypt + version prefix | **new** |
| `backend/app/core/config.py` | Add `APP_ENCRYPTION_KEY` + prod validator | edit |
| `backend/app/models/user.py` | Widen `mfa_secret` `String(64)` → `String(255)` | edit |
| `backend/app/services/mfa_service.py` | Encrypt on write; `_load_secret` decrypt helper on the 4 reads | edit |
| `backend/alembic/versions/encrypt_mfa_secret_0001_*.py` | Column widen + data migration | **new** |
| `backend/tests/test_mfa_encryption.py` | Unit + integration tests | **new** |
| `docs/DECISIONS.md` | ADR-002 → Implemented (after done) | edit |
| `docs/PROJECT_STATUS.md` | H2 checklist | edit |
| `docs/CHANGELOG.md` | Entry | edit |

No API routes, request/response schemas, or frontend changes — the wire contract
is unchanged.

---

## 4. Database Migration

**Revision:** `encrypt_mfa_secret_0001`
**down_revision:** `merge_heads_0001` (current single head — verified)

**Column width:** A Fernet token over a 32-char secret is ~140 chars; with the
`enc:v1:` prefix ~147. `String(64)` overflows, so the column is widened to
`String(255)`.

**`upgrade()`:**
1. `op.alter_column("users", "mfa_secret", type_=sa.String(255))`.
2. Data migration — for every row where `mfa_secret IS NOT NULL` **and** does not
   already start with `enc:v1:`: read plaintext, `encrypt_secret(...)`, write back.
   - Import the encryption helper from `app.core.crypto` so migration and runtime
     use identical logic/key.
   - Idempotent: prefixed rows are skipped, safe to re-run.

**`downgrade()`:**
- Reversible in principle (decrypt back to plaintext), but decryption *reduces*
  security and is only meaningful while the key exists. Recommendation: implement
  downgrade to decrypt rows back to plaintext and narrow the column, guarded so it
  no-ops if the key is unavailable. (Open question in §7 — confirm desired behavior.)

**Prerequisite:** `APP_ENCRYPTION_KEY` must be present in the environment when the
migration runs (CI, staging, prod). Deploy order: ship config/key → run migration.

---

## 5. Backward Compatibility

- **Existing enrolled users:** secrets are migrated in place; TOTP apps keep
  working with no re-enrollment. The secret value is unchanged — only its at-rest
  representation changes.
- **Deploy-before-migrate safety:** `decrypt_secret()` returns legacy plaintext
  unchanged when it sees no `enc:v1:` prefix, so the new code reads old rows
  correctly even before the data migration runs.
- **API/clients:** unchanged. Setup/enable/verify/disable/regenerate endpoints and
  payloads are identical.
- **Backup codes:** untouched (already hashed); users locked out of TOTP can still
  authenticate via backup codes.
- **Rollback:** code rollback alone is safe because old code can still read any row
  that was written as *plaintext*; rows already encrypted would be unreadable by
  old code — see Risks.

---

## 6. Testing Strategy

**Unit — `crypto.py`:**
- Round trip: `decrypt_secret(encrypt_secret(s)) == s`.
- Ciphertext carries the `enc:v1:` prefix and differs from plaintext.
- Non-determinism: two encryptions of the same secret differ (random IV).
- Legacy passthrough: `decrypt_secret("RAWBASE32...")` (no prefix) returns it unchanged.
- `decrypt_secret(None) is None`.
- Wrong/rotated key raises (`InvalidToken`).

**Integration — `mfa_service.py`:**
- After `generate_setup`, the DB column value starts with `enc:v1:` and is **not**
  the raw base32; but a TOTP built from the decrypted value verifies a live code.
- `enable_mfa` → `verify_totp` → `disable_mfa` full flow succeeds end-to-end.
- `regenerate_backup_codes` works with an encrypted secret.

**Migration:**
- Seed a user with plaintext `mfa_secret`, run `upgrade()`, assert stored value is
  `enc:v1:...` and decrypts to the original; a TOTP from it still verifies.
- Re-run `upgrade()` — no double-encryption (idempotent).

**Config:**
- `ENVIRONMENT=production` + default `APP_ENCRYPTION_KEY` raises on startup.

---

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Loss of `APP_ENCRYPTION_KEY`** → all MFA secrets become undecryptable, TOTP breaks for every user | High | Backup codes still work (separately hashed) so users aren't fully locked out; document key backup/escrow; treat key like `JWT_SECRET_KEY`. |
| Key missing in an environment/worker | High | Prod validator fails fast at startup; document required env var in deploy runbook. |
| Migration runs without key present | Med | Migration imports the same config; fails loudly rather than corrupting data. |
| Partial rollback: new code encrypts rows, then code is rolled back → old code can't read `enc:v1:` rows | Med | Version prefix makes them identifiable; document that rollback after new enrollments requires the downgrade migration (decrypt) or key stays available. |
| `String(255)` alter locks table briefly | Low | `users` is small in this deployment; alter is fast. |
| Fernet key format errors (not valid 32-byte base64) | Low | Validate/generate via documented command; fail fast at startup. |

**Open questions for approval:**
1. `downgrade()` — decrypt back to plaintext (reversible) **or** no-op like H1's
   irreversible downgrade? (Recommend: implement reversible decrypt for symmetry,
   since encryption *is* reversible.)
2. Dev default for `APP_ENCRYPTION_KEY` — ship a hardcoded dev Fernet key (like
   the dev `JWT_SECRET_KEY`) for zero-config local dev? (Recommend: yes.)

---

## 8. Acceptance Criteria

- [ ] `cryptography` added to `requirements.txt`; `app/core/crypto.py` provides
      `encrypt_secret` / `decrypt_secret` with `enc:v1:` versioning.
- [ ] New MFA enrollments persist `mfa_secret` as `enc:v1:` ciphertext — **no
      plaintext base32** is ever written.
- [ ] All existing plaintext secrets are encrypted by the migration; a post-migration
      scan finds **no** unprefixed non-null `mfa_secret` values.
- [ ] Login / verify / enable / disable / regenerate flows behave identically from
      the user's perspective; no re-enrollment required.
- [ ] `APP_ENCRYPTION_KEY` exists in config; production refuses the default value.
- [ ] Column widened to `String(255)`; migration is idempotent (safe re-run).
- [ ] All new unit, integration, and migration tests pass; existing auth/MFA tests
      remain green.
- [ ] ADR-002, PROJECT_STATUS.md, and CHANGELOG.md updated on completion.

---

**Do not implement until this specification is approved.**
