# Architecture Decision Records (ADR)

This document records important architectural decisions made during the development of Johnson CRM.

---

## ADR-001

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