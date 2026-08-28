# CRM Master Release Roadmap (FROZEN)

**Status:** authoritative, frozen. **Mode:** planning/audit only — no code, migration, DB, commit, push, PR, or deploy performed.
**Date:** 2026-08-20
**Derived from:** repository evidence (models/services/routers/tests/migrations/frontend/mobile), existing docs (`ROADMAP.md`, `PROJECT_STATUS.md`, `PRODUCT_VISION.md`), phase reports, and git/production audits.

---

## 1. Executive summary

This CRM is a **large, largely-complete multi-tenant SaaS** (96 backend models, 121 services, 90 API routers, 139 test files, 100 migrations, 81 frontend pages, 226 components, 321 mobile Kotlin files). Most product surface — foundation, CRM core, communications, analytics, automation, AI, a shipped Dental vertical, and a mobile app — **already exists and is in production** (older build `7382aee`).

The confusion over "Phase 4.1 / 4.2 / 4.3" comes from **two different numbering systems** colliding:
- the **original product ROADMAP** (`docs/ROADMAP.md`: 3 coarse phases), and
- a **later architecture-transformation program** (internally numbered "Phase 1→3.1→4.1→4.2→4.3") that converts the dental-specific CRM into a **generic configurable multi-industry platform**.

This document **freezes ONE authoritative major-phase roadmap** that absorbs both. **The transformation sub-phases (custom fields, custom objects, dynamic forms, builders) are NOT release milestones — they are Definition-of-Done items inside a single major phase.**

**TOTAL = 8 MAJOR PHASES. Currently at Phase 7. After Phase 7 + Phase 8 gates → RELEASE READY.**

## 2. Original roadmap (recovered)

`docs/ROADMAP.md` (the earliest plan):
- Phase 1 — Authentication, Organization, Users, Roles, Leads, Customers, Dashboard
- Phase 2 — Products, Inventory, Invoices, WhatsApp, SMS, Calling, Email
- Phase 3 — AI Assistant, Workflow Automation, Mobile Applications

`docs/PROJECT_STATUS.md` vision: *"multi-tenant, enterprise-grade CRM SaaS that serves 80% of service-based businesses through configurable workspaces from a single codebase."* (Its module table is stale — it predates almost all implementation.)

## 3. What changed during implementation

1. The product was built **feature-first and far beyond** the 3-phase sketch (full comms suite, 15+ analytics modules, a 14-module AI suite, automation engine, org/workforce, integrations, billing/plans/trials, a Dental vertical, and an Android app).
2. A **transformation program** was then started to generalize the dental-specific CRM into a configurable multi-industry platform. Its internal steps ("Phase 1 industry config → 2 dynamic modules → 3 generic core → 3.1 boundary guards → 4.1 custom fields → 4.2 custom objects → 4.3 dynamic forms") **expanded reactively** — which is what this freeze stops.
3. **This roadmap reframes that entire program as ONE major phase (Phase 7)** with a fixed DoD, so no further sub-phases appear.

**ORIGINAL ROADMAP vs LATER-DISCOVERED WORK is preserved above; nothing is silently rewritten.** The transformation was legitimate discovered work (§7 class A), now folded into a bounded phase.

## 4. Current project state (evidence-based)

| Area | Evidence | Status |
|---|---|---|
| Foundation (auth, org, users, RBAC, teams, branches) | routers + models + `test_super_admin`, `test_lead_security_matrix` | **COMPLETE** |
| CRM Core (leads, contacts, companies, customers, notes, activities, tasks, calendar, pipeline) | models/services/routers + lifecycle tests | **COMPLETE** |
| Communications (call/SMS/WhatsApp/email/templates/campaigns/notifications) | `whatsapp`,`sms`,`calling`,`email`,`campaigns` routers + `test_whatsapp_module` | **COMPLETE** |
| Analytics + Automation (dashboards, report builder, 15+ analytics, KPI/OKR; workflow/rules/events/queue/scheduler/SLA/escalation/approvals) | `report_builder`,`org_analytics`,`kpi`,`okr`,`workflows`,`rules`,`events`,`queue`,`scheduler`,`sla`,`escalation`,`approvals` routers | **COMPLETE** |
| AI Suite (platform, copilot, intelligence, KB, doc-intel, prediction, recommendation, governance) | `ai_platform`,`copilot`,`lead_intelligence`,… routers | **COMPLETE** |
| Industry vertical (Dental) + Mobile | 14 dental pages, `treatment_catalog`, invoicing; **321 mobile Kotlin files** | **COMPLETE (shipped to prod)**; mobile **PARTIALLY COMPLETE** (build unverified) |
| Configurable CRM engine | custom fields ✓, custom objects ✓; dynamic forms / builders pending | **IN PROGRESS** |
| Production readiness | `ops/*` backup/deploy/restore, migration hardening; staging/prod gate open | **IN PROGRESS** |

## 5. FINAL MAJOR PHASE COUNT

> ## **TOTAL: 8 MAJOR PHASES**

Phases were **not executed in strict numeric order** — the product was built feature-first (Phases 1–6), then generalized (Phase 7), with production hardening (Phase 8) interleaved. The numbering below is the **frozen logical structure**, not the build chronology.

## 6. Complete phase roadmap

| # | Phase | Status | Absorbs (former labels) |
|---|---|---|---|
| 1 | **Foundation & Multi-Tenancy** | ✅ COMPLETE | auth/org/users/RBAC/teams/branches |
| 2 | **CRM Core** | ✅ COMPLETE | leads/contacts/companies/customers/notes/activities/tasks/calendar/pipeline/order-to-cash |
| 3 | **Communications & Campaigns** | ✅ COMPLETE | call/SMS/WhatsApp/email/templates/campaigns/notifications |
| 4 | **Analytics, Reporting & Automation** | ✅ COMPLETE | dashboards/report-builder/analytics suite/KPI/OKR + workflow/rules/events/queue/scheduler/SLA/escalation/approvals |
| 5 | **AI Suite** | ✅ COMPLETE | AI platform/copilot/intelligence/KB/doc-intel/prediction/recommendation/governance/AI-API-SDK |
| 6 | **Industry Verticals & Mobile** | ✅ COMPLETE* | Dental module + Android app + integration hub + BI export |
| 7 | **Configurable CRM & Multi-Industry Engine** | 🔵 **IN PROGRESS ← WE ARE HERE** | transformation "Phase 1→3.1", Custom Fields "4.1"✓, Custom Objects "4.2"✓, Dynamic Forms "4.3", Pipeline/Stage Builder, Industry Template Builder, Config QA |
| 8 | **Production Readiness & Release** | 🟡 IN PROGRESS | security/observability/backup-restore/Alembic authority/staging/prod migration/deploy/perf/regression |
| — | **RELEASE READY** | ⛔ gated | all phases complete + §10 release gate |

*Phase 6 COMPLETE for shipped scope; mobile build verification rolls into Phase 8.

## 7. Definition of Done — every phase

**Phase 1 — Foundation & Multi-Tenancy.** *DoD:* auth (login/OTP/reset), org/tenant CRUD, user/seat mgmt, custom roles + RBAC, teams/branches, **tenant isolation enforced everywhere**. *Tests:* `test_super_admin`, `test_lead_security_matrix`, role/permission tests. *Gate:* zero cross-tenant leakage. **✅ met.**

**Phase 2 — CRM Core.** *DoD:* leads/contacts/companies/customers/notes/activities/tasks/calendar CRUD + dedup/merge/import/export; pipelines/stages + opportunity-as-lead×stage; order-to-cash. *Tests:* lifecycle + module tests. *Gate:* full CRUD + isolation. **✅ met.**

**Phase 3 — Communications & Campaigns.** *DoD:* call/SMS/WhatsApp/email providers + templates + campaigns + notifications + comm analytics. *Tests:* `test_whatsapp_module`, comms tests. *Gate:* send/receive + provider abstraction + isolation. **✅ met.**

**Phase 4 — Analytics, Reporting & Automation.** *DoD:* dashboards, report builder, analytics suite, KPI/OKR/goals; workflow/rules/events/queue/scheduler/SLA/escalation/approvals/notification-automation. *Tests:* module + analytics tests. *Gate:* safe query engine + automation runtime. **✅ met.**

**Phase 5 — AI Suite.** *DoD:* AI gateway (multi-provider), copilot, lead/comm/sales intelligence, KB (RAG), doc-intel, prediction, recommendation, prompt studio, AI governance/analytics, public AI API/SDK. *Gate:* provider-neutral, gated, governed. **✅ met.**

**Phase 6 — Industry Verticals & Mobile.** *DoD:* Dental vertical (patients/appointments/treatments/invoicing/dashboard/clinical RBAC) as a **gated overlay**; Android app; integration hub; BI export. *Gate:* vertical works, module-gated. **✅ met** (mobile build verification deferred to Phase 8).

**Phase 7 — Configurable CRM & Multi-Industry Engine (CURRENT).** *Objective:* make the CRM produce different industry CRMs from **configuration**, Core staying industry-neutral. *Included (each a DoD item, NOT a phase):*
1. Tenant industry configuration + business templates — ✅
2. Central module registry + dynamic routing + `require_module` gating — ✅
3. Generic CRM Core extraction + architecture boundary guards (industry→Core only) — ✅
4. **Custom Fields Engine** (13 types, validation, reserved keys) — ✅
5. **Custom Objects Engine** (definitions + JSON records + typed query engine + entity_reference) — ✅
6. **Dynamic Forms** (compose fields/objects into tenant-defined forms) — ⬜ **NEXT**
7. **Pipeline / Stage Builder** (configurable pipelines per industry) — ⬜
8. **Industry Template Builder** (assemble verticals from config) — ⬜
9. **Configuration QA + regression** (all of the above under one suite) — ⬜
*Exclusions:* new industry business logic in Core; workflow re-engineering; AI. *Tests:* `test_custom_fields`, `test_custom_objects`, `test_architecture_boundary`, `test_industry_scoping` + forms/builder suites. *Gate:* a non-dental tenant can be fully configured (fields+objects+forms+pipeline+template) with **zero Core code changes** and Core boundary guards green. **When items 6–9 pass → Phase 7 COMPLETE. No implicit "Phase 7.x".**

**Phase 8 — Production Readiness & Release.** *DoD:* Alembic as sole prod schema authority (`RUN_CREATE_ALL=false`); backup/restore verified; observability/structured logging; security review (authz, secrets, rate-limit, injection); performance/index review (incl. JSONB record indexes); **staging restore-and-verify of the release branch**; production migration + deploy + rollback drill; mobile build/release verification; full regression matrix. *Gate:* §10. **🟡 in progress** (staging/prod reconciliation already scoped in `production_staging_release_plan.md`).

## 8. Current completion matrix

| Phase | Status | Remaining work | Release-blocking |
|---|---|---|---|
| 1 Foundation | ✅ COMPLETE | — | no |
| 2 CRM Core | ✅ COMPLETE | — | no |
| 3 Communications | ✅ COMPLETE | — | no |
| 4 Analytics/Automation | ✅ COMPLETE | — | no |
| 5 AI Suite | ✅ COMPLETE | — | no |
| 6 Industry/Mobile | ✅ COMPLETE* | mobile build verification (→P8) | partial |
| 7 Configurable CRM | 🔵 IN PROGRESS | Dynamic Forms, Pipeline/Stage Builder, Industry Template Builder, Config QA | **YES** |
| 8 Production Readiness | 🟡 IN PROGRESS | `RUN_CREATE_ALL` transition, staging verify, prod migration+deploy, security/perf/observability, regression | **YES** |

## 9. Cross-phase dependencies

- Phases 1–6 are the **substrate** Phase 7 configures; all complete.
- **Phase 7 items build on each other:** custom fields (done) → custom objects (done) → dynamic forms → builders → config QA.
- **Phase 8 depends on Phase 7 reaching a releasable checkpoint** (see §11 — either ship current cc146e0 first, or finish Phase 7 then release).
- RELEASE READY depends on **both** Phase 7 complete **and** Phase 8 gate passed.

## 10. Production release gate (objective — "RELEASE READY")

RELEASE READY only when ALL hold:
1. Phases 1–8 DoD complete.
2. Backend `pytest` — pass (known redis/date-env flakes explained).
3. Frontend `vitest` + `tsc --noEmit` + production `build` — pass.
4. Alembic: single head, migrations verified on **real PostgreSQL** and on a **prod-data staging restore**; `RUN_CREATE_ALL=false`.
5. **Staging deployment** of the release branch against restored prod data — green.
6. Production-data compatibility: row counts preserved; catalog rename non-destructive.
7. Tenant isolation proven across all domains.
8. Security review passed (authz, secrets, rate-limit, injection, PII).
9. Regression matrix (core/dental/billing/WhatsApp/trials/custom-fields/objects/mobile) — green.
10. Backup + restore verified; rollback drill executed.
11. Deploy + health checks green; observability in place.

Individual features compiling or unit-passing is **not** release-ready.

## 11. What happens after the roadmap is frozen

Two valid sequencings (a **strategic choice for you**, not new phases):
- **Option R1 — Release-first:** run the Phase 8 staging/prod gate on the **current** `cc146e0` (Phases 1–6 + Custom Fields/Objects), ship it, then continue Phase 7 (Dynamic Forms → builders) in subsequent releases. *Reduces branch drift from prod; recommended.*
- **Option R2 — Feature-complete Phase 7 first:** finish Dynamic Forms + builders + config QA, then one larger Phase 8 release. *Bigger, later, riskier release.*

Either way, the **immediate next engineering task is Dynamic Forms** (the former "4.3") **as a Phase 7 DoD item** — begun only on your go.

## 12. STRICT ROADMAP GOVERNANCE RULE

> **No new major phase or sub-phase (no "Phase 7.x", "4.4", "9", etc.) may be introduced during implementation without explicit user approval.**

Any newly discovered work must first be classified as:
- **A — Existing-phase requirement** → folded into the relevant phase's DoD (default).
- **B — Technical debt** → logged; scheduled, not a phase.
- **C — Bug / blocker** → fixed within the current phase.
- **D — Post-release enhancement** → backlog, after RELEASE READY.
- **E — Genuine roadmap change** → **requires explicit user approval** before the roadmap count changes.

The roadmap count is **frozen at 8** unless the user approves a class-E change.

---

### One-line answer
**8 major phases. Phases 1–6 complete. We are at Phase 7 (Configurable CRM). After Phase 7 (next item: Dynamic Forms) + the Phase 8 production gate → RELEASE READY.**
