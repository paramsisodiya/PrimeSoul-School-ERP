# PrimeSoul School ERP — Comprehensive Module Roadmap

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Schools & Multi-Branch Institutions  
**Document Version**: 4.0  
**Status**: Official Product Development Roadmap  

---

## 1. Executive Status & Architectural Milestones

PrimeSoul School ERP is progressing through structured, safe commercialization phases. With the completion of the P0 Foundation (Phase 2), the complete Fees Engine & Financial UI (Phase 3), and Productization & Legacy Cleanup (Phase 4), the core enterprise platform is operational and production-ready.

---

## 2. Module Status Overview

### DONE (Completed & Verified)

1. **Foundation & Architecture**:
   - Centralized `django_school_management.core` architectural package.
   - Standard REST API envelopes, pagination, domain exceptions, and audit logging.
   - Comprehensive legacy code audit (`LEGACY_AUDIT.md`) and non-destructive isolation.
   - Zero-breakage database safety protocol.

2. **Multi-Tenancy**:
   - `School`, `Domain`, and `Subscription` models in `tenants` app.
   - `TenantMiddleware` providing automatic thread-local scoping, host resolution, and cross-tenant guards.
   - Abstract `TenantModel` and `TenantManager` guaranteeing data isolation across all tenant entities.

3. **RBAC (Role-Based Access Control)**:
   - 12 standardized system personas: Platform Super Admin, School Admin, Principal, Vice Principal, Academic Coordinator, Teacher, Accountant, Receptionist, Transport Manager, Librarian, Student, Parent.
   - Automated group synchronization and view-level authorization decorators (`@role_required`).

4. **Indian Academic Foundation**:
   - Native support for CBSE, ICSE, and State Board affiliation models.
   - `AcademicYear` supporting standard April 1 – March 31 Indian sessions with single active session constraints.
   - `GradeLevel` (Nursery to Class 12) and `Section` (A, B, C) replacing polytechnic semester structures.
   - `AcademicStream` (Science PCM/PCB, Commerce, Humanities) for Senior Secondary classes.

5. **Student / Parent / Teacher Foundation**:
   - `Student` master model with Indian statutory identifiers: Aadhaar Number, Permanent Education Number (PEN), APAAR ID, Category (General/OBC/SC/ST/EWS), Blood Group.
   - `ParentProfile` and `StudentGuardianRelationship` supporting multiple siblings per parent.
   - `TeacherProfile` with employee code, qualification, specialization, and fixed joining date.
   - `Designation` master for academic and administrative staff.

6. **Fees Backend**:
   - `FeeHead`, `FeeStructure`, `FeeStructureItem` templates per grade level.
   - `StudentFeeAssignment` with automatic installment generation (Monthly, Quarterly, Half-Yearly, Annual).
   - `FeeConcession` policies (Merit, Sibling, Staff, RTE 25% waiver) with administrative approval workflows.
   - Sequential, tamper-evident invoice numbering (`INV-YYYY-XXXXX`).

7. **Fees UI**:
   - Financial management hub with KPI cards, grade-wise fee collection progress bars, and recent transactions.
   - Interactive modals for fee head creation, structure configuration, and concession approval.
   - Installment tracker with overdue badges and balance calculations.

8. **Invoice / Payment / Receipt Ledger**:
   - Multi-mode offline collections: Cash, UPI, POS Card, Cheque (with drawer, bank, and clearance date tracking).
   - Sequential receipt generation (`RCP-YYYY-XXXXX`) with verification QR codes.
   - Production-grade ReportLab PDF generation for 80mm thermal and A4 official fee receipts.
   - Cryptographically verified online payment webhook infrastructure (Stripe, Razorpay-ready).

9. **Dashboard**:
   - Modern, responsive executive ERP Dashboard (`/dashboard/`).
   - Tenant school logo/name integration, academic session switcher, and user role badges.
   - Macro financial metrics, student strength counters, faculty counts, and pending approval widgets.

10. **Communication & Notification System (Phase 14)**:
    - Multi-channel notification delivery (In-App, Email, SMS, WhatsApp) with delivery tracking and audit logs.
    - Multi-target announcements (All School, Parents, Students, Teachers, Staff, Class, Section).
    - Notification preferences with emergency override, safe variable templates, and provider abstraction.

11. **Admissions Management (Phase 15)**:
    - Complete Indian K-12 admissions workflow: Enquiry -> Application -> Documents -> Review -> Interview/Assessment -> Approval -> Atomic Admission Conversion.
    - AdmissionSession & AdmissionClassConfig seat quota capacity management.
    - Transactional student/parent/enrollment provisioning, public online application foundation, and status lookup.

12. **Inventory & Asset Management (Phase 16)**:
    - Master Data: Category hierarchy, Unit of Measure, Supplier registry (Indian GSTIN validation regex), Store/Warehouse partitions, Inventory items with SKU and reorder thresholds.
    - Immutable Stock Ledger (`StockMovement`) supporting `IN`, `OUT`, `TRANSFER`, `ADJUSTMENT`, and `RETURN` operations.
    - Transactional Workflows: Goods Receipt Notes (GRN), Stock Issues to faculty/departments with non-negative stock guards, Inter-store transfers, and Stock adjustments.
    - Fixed Asset Register: Asset tagging (`AST-XXXXX`), serial numbers, warranty, lifecycle statuses (`AVAILABLE`, `ASSIGNED`, `IN_REPAIR`, `DISPOSED`, `RETIRED`), physical custody assignments, and maintenance logs.
    - PrimeSoul UI (27 templates) and REST APIs under `/api/v1/inventory/`.

13. **Advanced Reports & Analytics (Phase 17)**:
    - School Executive Decision Support Dashboard (`/reports/`) aggregating live database metrics across 9 functional domains (Students, Attendance, Academics, Examination, Finance, Admissions, Transport, Library, HR, Inventory).
    - Specialized Domain Reporting Engines with interactive date/academic year/grade filters and pure live ORM aggregations.
    - Export Engine: UTF-8 Excel-compatible CSVs with Byte Order Mark (BOM) and ReportLab branded PDF statements.
    - Security & Governance: Sensitive PII masking (PAN and Bank Accounts masked as `AB******4F` and `******1234`), portal user access blocking (HTTP 403 for Students & Parents), and multi-tenant isolation.
    - REST APIs under `/api/v1/reports/`.

---

### NEXT (Phase 5 & Production Hardening Scope)

1. **Academic Management**:
   - Subject-to-Class-Section mapping matrix for CBSE/ICSE curricula.
   - Class teacher allocation and section capacity management.
   - Master period timetable generation and room allocation.

2. **Student Management (Enhanced SIS)**:
   - Full student lifecycle: Inquiry -> Registration -> Online Application -> Verification -> Admission -> Roll Call -> Alumni.
   - Digital student ID card generation with Barcode/QR code.
   - Student document vault (Birth certificate, transfer certificate, previous marksheets).

3. **Attendance Management**:
   - Daily period-wise and morning-session student attendance recording.
   - Staff/faculty biometric and RFID integration with automated in/out logs.
   - Automated SMS/WhatsApp notifications to parents on student absence.
   - Monthly attendance percentage reports and CBSE minimum attendance threshold tracking (75%).

4. **Examination & Report Cards**:
   - CBSE CCE & Term Exam scheduling (Periodic Assessments, Mid-Terms, Annual Boards).
   - Marks entry portals with validation limits and grading scales (A1, A2, B1, etc.).
   - Automated CBSE-compliant PDF Report Card generation with scholastic and co-scholastic remarks.

5. **Communication Module**:
   - Centralized circulars, notices, and institutional bulletin board.
   - Multi-channel notification delivery: SMS (DLT-compliant Indian templates), WhatsApp Business API, and Email.
   - Direct teacher-to-parent messaging with audit logs.

6. **Transport Management**:
   - Fleet directory: Bus/van master, driver & conductor allocations, RC/fitness/insurance tracking.
   - Route and stop management with pickup/drop timings.
   - Student transport fee integration and automated billing.

7. **Library Management**:
   - ISBN book cataloging, Dewey Decimal / accession numbering.
   - Circulation desk: Issue, return, renewal, and lost book processing.
   - Automated late fine calculation integrated into fee invoice ledger.

8. **Certificates Engine**:
   - Transfer Certificate (TC) generator compliant with CBSE/State Board format.
   - Bonafide certificates, Character certificates, and Sports/Extracurricular certificates.
   - Verification portal with cryptographic QR codes to prevent forgery.

9. **Staff / Payroll Management**:
   - Staff salary structures (Basic, HRA, DA, Allowances, PF, ESI, TDS deductions).
   - Monthly payroll generation, payslip PDF rendering, and direct bank transfer exports.
   - Staff leave management (Casual, Medical, Earned) and leave balance tracking.

10. **Parent Portal**:
    - Dedicated parent login displaying children's attendance, fee dues, report cards, and notices.
    - 1-click online fee payment via UPI, debit card, and net banking with instant receipt download.

11. **Teacher Portal**:
    - Faculty dashboard for daily attendance marking, homework assignment, and marks entry.
    - Class timetable view and student performance analytics.

12. **SaaS Subscription & Billing**:
    - Tiered SaaS plans for institutional clients (Starter, Professional, Enterprise).
    - Automated license quota enforcement based on active student count.
    - Multi-tenant school onboarding wizard with custom domain mapping.

13. **Production Hardening**:
    - Django 4.2 LTS to Django 5.2 LTS upgrade.
    - Migration of legacy templates to modern PrimeSoul UI design system.
    - Deprecation removal of unused legacy fixtures, Bangladesh data dumps, and dead code.
    - End-to-end security penetration testing and Redis/Celery queue monitoring.
