# PrimeSoul School ERP — Legacy Audit & Decision Matrix

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Schools (CBSE, ICSE, State Boards) & Multi-Branch Institutions  
**Date**: September 2026  
**Status**: Authoritative Reference Document (Phase 4)

---

## 1. Overview & Decision Methodology

As part of the transformation into **PrimeSoul School ERP**, every component inherited from the upstream `Django-School-Management` project has been evaluated against:
1. **Multi-Tenant SaaS Architecture**: Capability to partition data strictly by school tenant (`school_id`).
2. **Indian K-12 Academic Relevance**: Compatibility with CBSE, ICSE, State Board grading, April–March fiscal/academic calendars, Nursery–Class 12 structure, and 11th/12th stream bifurcations.
3. **Enterprise Security & Reliability**: Resistance to IDOR, CSRF, insecure payment webhooks, and unauthenticated administrative actions.

### Decision Taxonomy
Each component is classified into exactly one of four mandatory statuses:
- **`KEEP`**: Essential, functional, and aligns with PrimeSoul standards. Retained as-is or already enhanced.
- **`REBUILD`**: Business concept is required for Indian K-12, but the legacy implementation is un-tenanted, insecure, or obsolete. Rebuild cleanly on modern PrimeSoul architecture.
- **`DEPRECATE`**: Retained in database schema and codebase for backward compatibility/historical data preservation, but isolated from modern customer-facing workflows.
- **`DELETE`**: Dead code, abandoned demo fixtures, unmaintained third-party adapters, or dangerous endpoints slated for scheduled removal in production hardening. *(Per Phase 4 safety rules, no files or tables are deleted in this phase)*.

---

## 2. Legacy Audit Matrix

| ITEM | LOCATION | PURPOSE | DECISION | REASON |
| :--- | :--- | :--- | :--- | :--- |
| **`tenants` App** | `django_school_management/tenants/` | Multi-tenant core: `School`, `Domain`, `Subscription`, `TenantModel`, `TenantMiddleware` | **`KEEP`** | Modern multi-tenant SaaS foundation implemented in Phase 2; critical for tenant isolation. |
| **`fees` App** | `django_school_management/fees/` | Comprehensive Indian K-12 fee management, installments, concessions, receipts, PDF generation | **`KEEP`** | Production-grade Indian fee engine built in Phase 3; 100% verified and tested. |
| **`accounts` App (Custom User & RBAC)** | `django_school_management/accounts/` | Custom `User` model, 12 standardized system roles, tenant-scoped authentication | **`KEEP`** | Central auth and identity layer hardened in Phase 2; integral to system operation. |
| **`accounts.views.dashboard`** | `django_school_management/accounts/views.py` | Main executive ERP dashboard view | **`KEEP`** | Modernized in Phase 3 with PrimeSoul KPI metrics, executive quick-actions, and role scoping. |
| **`GradeLevel` & `Section` Models** | `django_school_management/academics/models.py` | Indian K-12 classes (Nursery to 12th) and sections (A, B, C) | **`KEEP`** | Built in Phase 2 to represent standard Indian school hierarchies. |
| **`AcademicYear` Model** | `django_school_management/academics/models.py` | Tenant-scoped April 1 – March 31 academic sessions with unique current session guard | **`KEEP`** | Core Indian academic calendar foundation. |
| **`AcademicStream` Model** | `django_school_management/academics/models.py` | Senior secondary streams (Science PCM/PCB, Commerce, Humanities) | **`KEEP`** | Essential for CBSE/ICSE Classes 11 and 12. |
| **`Student` Model (Indian K-12)** | `django_school_management/students/models.py` | Student master record with Aadhaar, PEN, APAAR, Blood Group, Category, roll number | **`KEEP`** | Replaces polytechnic applicant model for primary school operations. |
| **`ParentProfile` & Relationship** | `django_school_management/students/models.py` | Guardian master records supporting multiple siblings and parental portal access | **`KEEP`** | Built in Phase 2; replaces flat string father/mother columns. |
| **`TeacherProfile` Model** | `django_school_management/teachers/models.py` | Faculty profile linked 1-to-1 to User with employee code, qualifications, joining date | **`KEEP`** | Fixed legacy auto_now bug and hardened staff records. |
| **`Designation` Model** | `django_school_management/teachers/models.py` | Staff designation master (Principal, PGT, TGT, PRT, Admin) | **`KEEP`** | Tenant-scoped staff classification. |
| **`core` Architecture Module** | `django_school_management/core/` | Unified domain boundary: context, roles, permissions, audit logging, exceptions | **`KEEP`** | Centralized in Phase 4 to cleanly govern all cross-cutting ERP infrastructure. |
| **`utils.health_view`** | `django_school_management/utils/views.py` | System health check (`/health/`) verifying database and cache connectivity | **`KEEP`** | Essential for load balancers and Kubernetes container liveness probes. |
| **`InstituteProfile` Model** | `django_school_management/institute/models.py` | Legacy singleton school profile with `active=True` constraint | **`DEPRECATE`** | Replaced by `tenants.School` for multi-tenancy. Maintained for legacy template compatibility. |
| **`Department` Model** | `django_school_management/academics/models.py` | Polytechnic academic department entity | **`DEPRECATE`** | Polytechnic concept. Indian K-12 uses `GradeLevel` and `AcademicStream`. Kept for migration safety. |
| **`AcademicSession` Model** | `django_school_management/academics/models.py` | Legacy calendar session (un-tenanted) | **`DEPRECATE`** | Replaced by tenant-scoped `AcademicYear`. Retained to avoid breaking legacy foreign keys. |
| **`Semester` Model** | `django_school_management/academics/models.py` | Polytechnic 1st to 8th semester terms | **`DEPRECATE`** | Replaced by `GradeLevel` and `Section`. Retained for legacy subject groups and result records. |
| **`Subject` Model (Legacy)** | `django_school_management/academics/models.py` | Subject master with theory/practical marks | **`REBUILD`** | Currently tied to legacy `Department`. Must be rebuilt to bind directly to `GradeLevel` & `AcademicStream`. |
| **`SubjectGroup` & `Assign`** | `django_school_management/result/models.py` | Grouping of subjects per department and semester | **`REBUILD`** | Will be rebuilt in Phase 5 as Class-Section Subject Allocations under Examinations. |
| **`AdmissionStudent` Model** | `django_school_management/students/models.py` | Legacy polytechnic admission applicant record with SSC/HSC scores and quotas | **`DEPRECATE`** | Replaced by `Student` model. Kept to preserve historical applicant data. |
| **`Counseling` Model & Views** | `django_school_management/students/` | Polytechnic quota counseling and department selection workflow | **`DEPRECATE`** | Polytechnic tertiary admission workflow, irrelevant to Indian K-12 schools. Will be replaced by standard K-12 Inquiry & Admission. |
| **`Teacher` (Legacy Model)** | `django_school_management/teachers/models.py` | Original unlinked teacher record with `joining_date auto_now=True` bug | **`DEPRECATE`** | Replaced by `TeacherProfile`. Retained for historical foreign key constraints. |
| **`payments` App (Legacy)** | `django_school_management/payments/` | Legacy flat payment table and SSLCommerz transaction history | **`DEPRECATE`** | Replaced by enterprise `PaymentTransaction` and `FeeReceipt` in `fees` app. |
| **`pages.payment_views.sslpay`** | `django_school_management/pages/payment_views/` | SSLCommerz payment gateway redirect and session generator | **`DEPRECATE`** | Bangladesh-only payment gateway. PrimeSoul uses Razorpay, Stripe, and Cashfree for India. |
| **Insecure GET Payment Callbacks** | `django_school_management/pages/views.py` | Auto-confirming admission payment merely upon visiting success redirect URL | **`DEPRECATE`** | Neutralized in Phase 2. Replaced with cryptographically signed webhooks. |
| **`articles` App** | `django_school_management/articles/` | Public blog and newsletter article publishing app | **`DEPRECATE`** | Non-core to ERP operations. To be rebuilt under a unified `communication` module. |
| **`notices` App** | `django_school_management/notices/` | PDF notice board with separate public and dashboard views | **`REBUILD`** | Useful for schools, but lacks multi-tenancy and push notifications. Rebuild in `communication` module. |
| **`curriculum` App** | `django_school_management/curriculum/` | Bangladesh Madrasah (Ebtedayi/Dakhil) and polytechnic curriculum library | **`DEPRECATE`** | Contains Bangladesh-specific curricula fixtures. Indian K-12 uses CBSE/ICSE curriculum templates. |
| **`EducationBoard` Model (BD)** | `django_school_management/institute/education_boards.py` | Bangladesh BISE boards (Dhaka, Chittagong, Madrasah Board) | **`DEPRECATE`** | Replaced by CBSE, ICSE, CISCE, and Indian State Boards in `tenants.School`. |
| **`result` App (Legacy)** | `django_school_management/result/` | Polytechnic semester GPA and marks entry system | **`REBUILD`** | Not compliant with CBSE CCE/term assessment rules or Indian report card standards. Rebuild as `examinations`. |
| **`pages` App** | `django_school_management/pages/` | Public marketing landing page, about, contact, and online admission form | **`REBUILD`** | Hardcoded templates with outdated styling. Rebuild as tenant-configurable public portal. |
| **`seed.py` (Bangladesh Fixtures)** | Project root: `seed.py` | Database seeding script loading Bangladesh cities and districts | **`DELETE`** | Slated for replacement with Indian states, districts, and CBSE demo school seeder. |
| **`datadump_pretty.json` & `dump.json`**| Project root | 2MB legacy database dumps containing Bangladesh polytechnic demo data | **`DELETE`** | Slated for deletion in production hardening once Indian demo fixtures are finalized. |
| **`admin_honeypot` Configuration** | `config/settings/base.py`, `config/urls.py` | Outdated honeypot package commented out due to Django 4 incompatibility | **`DELETE`** | Dead commented references. Real firewall/WAF rate limiting should be used instead. |
| **`django-file-form` (Legacy Upload)** | `config/urls.py` | Upload helper for multi-file forms | **`DEPRECATE`** | Can be replaced with native Django formsets or direct S3/cloud storage uploads. |
| **`ckeditor` / `ckeditor_uploader`** | `config/settings/base.py`, `requirements.txt` | CKEditor 4 WYSIWYG editor | **`DEPRECATE`** | CKEditor 4 reached End-of-Life (EOL) in 2023. Plan migration to TinyMCE 6 or modern headless editor. |
| **`bootstrap4` & `crispy-bootstrap4`** | `requirements.txt`, templates | Bootstrap 4.6 frontend framework | **`REBUILD`** | Deprecated upstream. Modern PrimeSoul UI targets Bootstrap 5 / Tailwind CSS. |
| **`jquery-3.4.1.min.js`** | `static/js/jquery-3.4.1.min.js` | Legacy jQuery version with known CVEs in older sub-releases | **`REBUILD`** | Modernize to jQuery 3.7.1+ or eliminate jQuery entirely in favor of modern ES6 JavaScript. |
| **Adminator Dashboard Assets** | `static/` | Adminator Bootstrap template styles, vendor bundles | **`REBUILD`** | Heavy monolithic bundle; will be replaced by modular PrimeSoul Design System in Phase 5. |

---

## 3. Bangladesh & Polytechnic Specific Terminology Catalog

The following legacy terminology has been cataloged across code, database schemas, and documentation:

1. **Academic Terms**:
   - `Semester` (1st through 8th) -> Transitioning to `Class / Grade` (Nursery to 12th) and `Term / Semester` (Term 1 / Term 2).
   - `Department` -> Transitioning to `Grade Level` and `Academic Stream` (Science, Commerce, Arts).
   - `Shift` (Morning / Day) -> Retained as optional branch operational attribute.
   - `SSC` / `HSC` / `Dakhil` / `JDC` / `Vocational` -> Transitioned to Indian boards (`CBSE Class X`, `CBSE Class XII`, `ICSE`, `State Board`).
   - Direct 4th semester admission for HSC Science passers -> Isolated as polytechnic legacy rule; non-functional in K-12.

2. **Regional & Administrative Terms**:
   - `Freedom Fighter Quota` & `Tribal Quota` -> Retained as legacy fields; Indian admissions utilize RTE (Right to Education 25%), General, OBC, SC, ST, EWS.
   - `BDT` Currency -> Replaced with `INR` (`₹`) as system standard.
   - `Asia/Dhaka` Timezone -> Replaced with `Asia/Kolkata` as system standard.
   - `SSLCommerz` -> Deprecated; Indian gateways (Razorpay, Stripe, Cashfree) prioritized.

---

## 4. Architectural Boundaries for Phase 5

In Phase 5, newly built modules will be created strictly inside the approved PrimeSoul domain architecture:
```
django_school_management/
├── core/                # Centralized infrastructure (Tenant context, RBAC, Audit, Exceptions)
├── tenants/             # Multi-tenancy, Schools, Subscriptions, Domains
├── accounts/            # Users, Authentication, User Profile, Roles
├── academics/           # Academic Years, Grades, Sections, Streams, Class Timetables
├── students/            # Student SIS, Parent Directory, Enrollment, ID Cards
├── teachers/            # Faculty, Staff Directory, Department Heads, Qualifications
├── attendance/          # [PHASE 5] Daily student attendance, Teacher attendance, Biometric/RFID
├── examinations/        # [PHASE 5] Exams, Assessment schemes, Marks entry, Report cards, Grading
├── fees/                # Fee heads, Structures, Invoices, Offline/Online payments, Receipts
├── communication/       # [PHASE 5] Notices, Circulars, SMS/WhatsApp alerts, Email broadcasts
├── transport/           # [PHASE 5] Vehicles, Routes, Stops, Driver allocations, Transport fees
├── library/             # [PHASE 5] Books, Cataloging, Issue/Return, Fines
├── certificates/        # [PHASE 5] Transfer Certificates (TC), Bonafide, Character, Marksheets
├── payroll/             # [PHASE 5] Staff salary structures, Payslips, Allowances, Deductions
├── subscriptions/       # SaaS billing for school institutions
└── notifications/       # Internal notification dispatchers
```

No existing tables or migrations will be destroyed. All new modules will cleanly inherit from `core.models.TenantModel`.
