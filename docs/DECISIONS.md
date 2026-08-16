# Architecture Decision Records (ADR)

This document records important architectural decisions made during the development of Johnson CRM.

---

## ADR-001
Status

Implemented

Implementation

Completed during Sprint 1.

Migration added.

Unit tests added.

Reviewed.

Approved.
### Title
Hash Refresh Tokens at Rest

### Status
Approved

### Date
2026-08-03

### Problem

Refresh tokens are currently stored in plaintext in the database.
If the database is compromised, active user sessions can be hijacked.

### Decision

Store only the SHA-256 hash of the refresh token.

Clients will continue sending the original refresh token.

The server will hash incoming tokens before validation.

### Consequences

- Improved database security
- Existing API remains unchanged
- Requires one-time migration

---

## ADR-002

### Title

Encrypt MFA Secret

### Status

Approved

### Date

2026-08-03

### Problem

TOTP secrets are stored in plaintext.

### Decision

Encrypt secrets before persisting.

Use APP_ENCRYPTION_KEY.

### Consequences

Database compromise will not expose MFA secrets.

---

## ADR-003

### Title

Per Account Lockout

### Status

Approved

### Date

2026-08-03

### Problem

Authentication only has IP-based rate limiting.

### Decision

Track failed login attempts.

Lock accounts temporarily after configurable failures.

### Consequences

Reduced brute-force attacks.

Configurable security.

---

## ADR-004

### Title
Centralized Email Normalization

### Status
Approved

### Date
2026-08-03

### Problem
Previously, email normalization was scattered across a few write paths and lookups using case-insensitive checks or manual lowercasing. Five other write paths stored mixed-case emails, risking case-variant duplicate accounts and unstable lookups.

### Decision
Implement email normalization at the SQLAlchemy ORM column boundary using a custom `NormalizedEmail` TypeDecorator on `User.email` and `UserInvitation.email`. Create a pure `normalize_email()` function as the single source of truth for Unicode NFC normalization, trimming, and lowercasing without stripping subaddress tags/dots. Add a functional unique index on `lower(email)` in the database and enforce it via Alembic migrations.

### Consequences
- Single choke point for all email writes, updates, and comparisons.
- Guaranteed case-insensitive lookups automatically without scattered `.lower()` or `func.lower()` calls.
- Prevent case-variant duplicate account registrations.
- Loud pre-flight check in database migration to detect and reject duplicate case-variant emails before updating the database.