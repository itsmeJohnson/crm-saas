# Changelog

All notable changes to this project will be documented in this file.

---

## v0.8.0 - Metadata Engine Foundation (2026-08-04)

### Added
- **Multi-Tenant Custom Fields**: Support for custom metadata fields per tenant organization without database schema changes.
- **Multi-Pipeline Sales Architecture**: Enabled multiple active pipelines and stage configurations for advanced deal orchestration.
- **Metadata Bootstrap API**: Single high-performance API endpoint to download all tenant pipeline configurations and metadata definitions.
- **Metadata Versioning**: Integer-based versioning at the organization level to coordinate cache updates.
- **Validation Engine**: Added required, min/max length, unique value, custom regex rules, and pre-validation normalization.
- **Redis Metadata Cache**: Fast query responses using Redis cache invalidation keyed by module names.
- **Lead Integration**: Custom JSONB field backing for dynamic attributes.
- **Enterprise Audit Logging**: Secure change capture for pipeline structure and metadata definition edits.

### Fixed
- **Regression Suite Alignment**: Aligned and successfully executed all 923 backend regression test cases.
