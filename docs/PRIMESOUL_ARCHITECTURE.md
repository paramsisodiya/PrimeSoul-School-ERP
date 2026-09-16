# PrimeSoul School ERP — Architecture & Technical Reference

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Schools (CBSE, ICSE, State Boards, IB, Cambridge) + Multi-Branch Educational Groups  
**Document Version**: 4.0 (Commercial Architecture & Productization)  
**Status**: Authoritative Architectural Baseline  

---

## 1. Executive Summary & Product Architecture

**PrimeSoul School ERP** is a modern, production-grade, multi-tenant Software-as-a-Service (SaaS) platform engineered specifically for Indian K-12 schools, CBSE/ICSE institutions, and multi-branch educational trusts.

### Core Architectural Pillars:
1. **Strict Multi-Tenancy**: Isolated school data partitioned by `school_id` with thread-local and middleware-level scoping (`TenantMiddleware`).
2. **Indian K-12 Academic Foundation**: Native CBSE/ICSE/State Board structures, April–March financial/academic sessions, Nursery through Class 12 grade progressions, and 11th/12th stream bifurcations (Science PCM/PCB, Commerce, Humanities).
3. **Statutory & Institutional Compliance**: Dedicated models for Aadhaar, Permanent Education Numbers (PEN), APAAR IDs, and UDISE+ institution codes.
4. **Hardened Financial Operations**: Deterministic double-entry ledger, sequential invoice/receipt numbering (`INV-YYYY-XXXXX`, `RCP-YYYY-XXXXX`), partial installment allocation, offline/online multi-mode settlement (Cash, UPI, Cheque, POS), and cryptographic webhook processing.
5. **Zero-Trust Role-Based Access Control (RBAC)**: 12 standardized enterprise personas with view-level and API-level tenant guards.

```
                  ┌──────────────────────────────────────────────┐
                  │                 DNS / Gateway                │
                  │   *.primesoul.in  /  customschooldomain.com  │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │             TenantMiddleware                 │
                  │  1. Authenticated User's School              │
                  │  2. Subdomain / Custom Domain Resolution     │
                  │  3. Thread-Local Context Binding (request.tenant)
                  └──────────────────────┬───────────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
            ┌───────────────────────────┐ ┌───────────────────────────┐
            │   Central Core & RBAC     │ │  Tenant-Scoped Models     │
            │  - django_school_management.core  │ - School / Domain / Plan │
            │  - 12 System Personas     │ │  - AcademicYear / Grade   │
            │  - Audit Logging Engine   │ │  - Student SIS / Parent   │
            │  - Standard API Envelopes │ │  - Fee Invoices & Receipts│
            └───────────────────────────┘ └───────────────────────────┘
```

---

## 2. Target 16-Module Domain Architecture

PrimeSoul ERP organizes institutional capabilities into 16 discrete, modular packages. Each module maintains strict separation of concerns, referencing shared tenant abstractions through `core.models.TenantModel`.

```
django_school_management/
├── core/                # Centralized infrastructure: context, RBAC, audit, exceptions, API envelopes
├── tenants/             # Multi-tenancy engine: School, Domain, Subscription, TenantMiddleware
├── accounts/            # Users, Authentication, User Profile, Roles, Password Reset
├── academics/           # Academic Years (Apr-Mar), Grades, Sections, Streams, Timetables
├── students/            # Student SIS, Parent Directory, Guardian Links, Enrollment
├── teachers/            # Faculty, Staff Directory, Department Heads, Designations
├── attendance/          # [PHASE 5] Daily student attendance, Staff attendance, Biometric/RFID integration
├── examinations/        # [PHASE 5] CBSE/ICSE exam schemes, Marks entry, CCE grading, Report cards
├── fees/                # Fee heads, Structures, Concessions, Invoices, Payments, Receipts, PDFs
├── communication/       # [PHASE 5] Circulars, Notice board, SMS/WhatsApp gateways, Email broadcasts
├── transport/           # [PHASE 5] Bus routes, Vehicles, Stops, Allocations, Transport billing
├── library/             # [PHASE 5] Book catalog, ISBN, Issue/Return tracking, Fines
├── certificates/        # [PHASE 5] Transfer Certificates (TC), Bonafide, Character, Study certificates
├── payroll/             # [PHASE 5] Staff salary components, Monthly payroll runs, Payslips, Deductions
├── subscriptions/       # Platform-level SaaS subscription billing for schools
└── notifications/       # Cross-module async notification dispatcher (Celery-driven)
```

---

## 3. Core Architecture (`django_school_management.core`)

To eliminate code duplication, circular dependencies, and fragmented utility scripts, PrimeSoul centralizes common system patterns into `django_school_management.core`:

1. **`core.context`**:
   - `get_current_school()` / `get_current_tenant()`: Thread-safe accessor for the active request tenant.
   - `set_current_school()` / `clear_current_school()`: Context lifecycle binders used by middleware and async tasks.
2. **`core.models`**:
   - `TenantModel`: Abstract model equipping entities with an indexed `school = ForeignKey(School, on_delete=CASCADE)` and `objects = TenantManager()`.
   - `TenantManager` / `TenantQuerySet`: Automatic query-level data isolation preventing cross-tenant leakage.
3. **`core.roles`**:
   - `Role`: Standardized 12 system personas: `PLATFORM_SUPER_ADMIN`, `SCHOOL_ADMIN`, `PRINCIPAL`, `VICE_PRINCIPAL`, `ACADEMIC_COORDINATOR`, `TEACHER`, `ACCOUNTANT`, `RECEPTIONIST`, `TRANSPORT_MANAGER`, `LIBRARIAN`, `STUDENT`, `PARENT`.
   - `ensure_system_roles_exist()`: Automated Django Group synchronizer.
4. **`core.permissions`**:
   - `@role_required(*allowed_roles)`: Enforces role assignment and tenant scoping on view endpoints.
   - `require_school_access(user, school)`: Strict cross-tenant validation ensuring non-superusers cannot access foreign tenant records.
5. **`core.audit`**:
   - `log_audit_event()`, `log_security_event()`, `log_financial_event()`: Structured audit logger tracking actor, school, resource, action, IP, and payload details for compliance.
6. **`core.exceptions`**:
   - `PrimeSoulERPException`, `TenantIsolationError`, `AcademicSessionClosedError`, `FinancialPeriodLockedError`.
7. **`core.responses`**:
   - `api_success()`, `api_error()`: Consistent REST JSON envelopes (`status`, `message`, `data`, `meta`, `errors`).
   - `StandardResultsSetPagination`: Page-number pagination standard (25 items/page default).
8. **`core.constants`**:
   - Indian defaults: `INR` (`₹`), `Asia/Kolkata`, board choices (`CBSE`, `ICSE`, `STATE`, `IB`, `CAMBRIDGE`).

---

## 4. Multi-Tenancy Strategy

### 4.1 Tenancy Model: Shared Database with Discriminator Column
PrimeSoul utilizes a **Shared Database, Shared Schema with Discriminator Column (`school_id`)** pattern. This optimizes cost efficiency, multi-tenant density, database connection pooling, and simplifies automated schema migrations across thousands of branches.

### 4.2 Resolution Lifecycle (`TenantMiddleware`)
Every HTTP request follows a strict 4-step tenant resolution chain:
1. **Explicit Development / API Headers**:
   - `X-Tenant-Slug`, `X-Tenant-ID`, or `?tenant=slug` query parameter.
2. **Custom Domain Matching**:
   - Host matching against verified `Domain` instances (e.g., `dpsrkpuram.ac.in`).
3. **Subdomain Matching**:
   - Host prefix matching against `*.primesoul.in` or `*.localhost` (e.g., `dpsrkpuram.primesoul.in`).
4. **Authenticated User School Scope**:
   - Fallback to `request.user.school`.
   - **Cross-Tenant Guard**: If an authenticated non-superuser belonging to School A attempts to access School B via host spoofing, the middleware aborts with `HTTP 403 Forbidden`.

---

## 5. URL Architecture & Navigation Routing

PrimeSoul ERP implements clean, predictable routing for both customer-facing UI and REST APIs:

### 5.1 Main Commercial URL Structure
| Route | Handler / App | Description |
| :--- | :--- | :--- |
| `/` | `pages.views.landing` | Public institutional portal / landing page |
| `/dashboard/` | `accounts.views.dashboard` | Executive KPI dashboard & Quick Action center |
| `/academics/` | `academics.urls` | Academic sessions, classes, sections, and subjects |
| `/students/` | `students.urls` | Student enrollment, SIS directory, and admissions |
| `/teachers/` | `teachers.urls` | Faculty directory, profiles, and designations |
| `/fees/` | `fees.urls` | Financial center: fee heads, structures, installments, invoices, payments, receipts |
| `/accounts/` | `allauth.urls` | Enterprise authentication (login, logout, password recovery) |
| `/notices/` | `notices.urls` | School circulars and public bulletin board |
| `/blog/` | `articles.urls` | Institutional articles and newsletter |
| `/settings/` | `accounts.urls` & `institute.urls` | Institutional profile, tenant domains, users, and approvals |
| `/health/` | `utils.views.health_view` | Container liveness and infrastructure health probe |
| `/admin/` | `django.contrib.admin` | Platform superadmin management console |

### 5.2 Future Phase 5 Expansion Routes
- `/attendance/`: Daily student & teacher attendance registers, RFID/biometric logs.
- `/examinations/`: Assessment schedules, marks entry, CCE report cards.
- `/transport/`: Bus tracking, fleet management, student route allocations.
- `/library/`: Books catalog, circulation desk, overdue fees.
- `/certificates/`: TC and bonafide certificate generator.
- `/payroll/`: Staff compensation, monthly payroll runs, salary slips.

### 5.3 REST API Versioning
All programmatic endpoints adhere to URI versioning:
- `/api/v1/fees/`: Fees, invoices, payments, and receipts.
- `/api/v1/academics/`: Academic structures and subjects.
- `/api/v1/students/`: Student SIS and parent relationships.
- `/api/v1/teachers/`: Faculty and staff profiles.
- `/api/v1/docs/`: Interactive Swagger/OpenAPI documentation.

---

## 6. Database Safety & Migration Invariants

1. **Zero Destructive Actions**: Never drop tables, reset migration sequences, or execute destructive schema squashes on active environments.
2. **Nullable Legacy Compatibility**: All legacy references (`InstituteProfile`, `Department`, `AdmissionStudent`) remain nullable in database schemas to prevent migration breaks.
3. **Reversible Migrations**: Every new schema change must be accompanied by explicit forward and backward migration methods.
4. **Automated Validation**: Migrations must execute cleanly from scratch on CI/CD pipelines without `--fake` or manual intervention.
