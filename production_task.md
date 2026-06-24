# Production Hardening Sprint v1.0 Tasks

## P0 - Critical Security
- [x] 1. Password Reset Hardening
  - [x] Hash token in user model (SHA256)
  - [x] Configure secure SMTP settings or fallback console logging
  - [x] Add password reset templates
  - [x] Update /forgot-password to send emails and NOT expose token in API response
  - [x] Update /reset-password logic to verify hash
  - [x] Add rate limiting or security assertions
  - [x] Add tests for password reset hardening
- [x] 2. File Upload Security
  - [x] Enforce mime-type, magic bytes, and extension validations (jpg, jpeg, png, webp, svg, pdf)
  - [x] Validate max 2MB file size
  - [x] Implement random file name generation
  - [x] Ensure files are stored outside public directories
  - [x] Add tests for file upload validations
- [x] 3. DigitalOcean Spaces Storage Provider
  - [x] Write StorageProvider with DO Spaces client configuration
  - [x] Modify upload/delete endpoints to use cloud storage provider
  - [x] Write cleanup & lifecycle methods

## P0 - Billing
- [x] 1. Razorpay Payment Gateway Integration
  - [x] Create Razorpay client service integration
  - [x] Implement subscription and invoice payment endpoints
  - [x] Add webhook endpoint with signature verification, retries, and refunds

## P0 - Cron
- [x] 1. Distributed Scheduler
  - [x] Implement Redis-based distributed lock (`cron_lock`)
  - [x] Guard cron jobs inside main app to prevent concurrent duplicates

## P1 - Performance
- [x] 1. Caching Feature Guards
  - [x] Implement cache checking in `require_feature` dependency
  - [x] Add invalidation triggers on subscription/plan changes
- [x] 2. DB Indexing & N+1 Queries
  - [x] Generate Alembic migrations for missing FK indexes
  - [x] Resolve any identified queries causing duplicate hits

## P1 - Backups
- [x] 1. Cloud Database Backup routine
  - [x] Update database backup shell script to push to DO Spaces bucket
  - [x] Set up backup rotation rules

## P1 - Production Config
- [x] 1. Enforce strict configuration secrets
  - [x] Create `.env.production.example` without default passwords or keys
  - [x] Disallow dev setups under production profiles

## P1 - Monitoring
- [x] 1. Expose system metrics
  - [x] Setup Prometheus instrumentation endpoint

## P2 - Structured Logging
- [x] 1. Request logging
  - [x] Implement JSON formatting middleware with request/correlation IDs

## P2 - CI/CD
- [x] 1. GitHub Actions
  - [x] Configure workflow files for build, test, lint, and deploy check

## Testing & Load Verification
- [x] 1. Load test suite setup
  - [x] Write test execution scripts
