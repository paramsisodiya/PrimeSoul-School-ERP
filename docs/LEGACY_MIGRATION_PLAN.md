# PrimeSoul School ERP — Legacy Migration Plan

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Schools  
**Document Version**: 4.0  
**Status**: Authoritative Reference  

---

## 1. Migration Overview & Strategic Principles

The transition from the legacy `Django-School-Management` polytechnic single-institute codebase to **PrimeSoul School ERP** (Multi-Tenant SaaS) must guarantee 100% database safety and continuity.

### Core Guiding Principles:
1. **Zero Data Loss**: Existing database records in `db.sqlite3` or PostgreSQL production databases must remain entirely intact.
2. **Schema Invariance**: No database tables are dropped, no migrations are forcibly squashed, and no historical migration files are deleted in this phase.
3. **Additive-First Schema Evolution**: All new PrimeSoul capabilities (Tenants, Indian K-12 Academic Models, Student SIS, Fees Ledger) are added as cleanly namespaced, additive migrations with nullable foreign keys to legacy models where necessary.
4. **Gradual Isolation**: Legacy polytechnic and Bangladesh-specific workflows (Counseling, SSC/HSC Direct 4th semester, BDT payment redirects) are bypassed by modern UI/API routes while remaining intact in the schema for historical auditing.

---

## 2. Legacy Model to PrimeSoul Entity Mapping

| Domain Area | Legacy Implementation | PrimeSoul Model | Migration Status & Compatibility Strategy |
| :--- | :--- | :--- | :--- |
| **Tenancy** | Singleton `InstituteProfile` (`active=True`) | `School`, `Domain`, `Subscription` | Modern multi-tenancy operational. Legacy `institute` foreign keys retained as nullable to ensure existing records load without error. |
| **RBAC / Identity** | String check on `User.requested_role` | `User.school` + `Role` enum (12 roles) + Django Groups | Role synchronization automated. Legacy roles mapped to `SCHOOL_ADMIN` or `TEACHER`. |
| **Academic Session** | Un-tenanted `AcademicSession` | `AcademicYear` (April 1 – March 31) | Scoped per tenant school. Legacy sessions preserved for historical result references. |
| **Grade / Class** | Polytechnic `Department` | `GradeLevel` (Nursery to Class 12) | Indian K-12 grades introduced. Legacy `Department` models remain in DB; modern UI uses `GradeLevel`. |
| **Sections** | Polytechnic `Semester` (1st–8th) | `Section` (A, B, C) | Sections linked directly to `GradeLevel`. Legacy `Semester` model preserved for historical grades. |
| **Academic Streams** | None (ad-hoc groups) | `AcademicStream` (Science, Commerce, Arts) | Introduced for Classes 11 and 12. |
| **Student SIS** | `AdmissionStudent` (polytechnic applicant) | `Student` (Indian K-12 Master) | Native Aadhaar, PEN, APAAR ID, Category, Blood Group. Legacy applicants remain for counseling records. |
| **Parent Directory** | Flat string fields (`father_name`, `mother_name`) | `ParentProfile`, `StudentGuardianRelationship` | Normalized guardian profiles supporting multiple siblings per parent. |
| **Teacher Profiles** | `Teacher` (`auto_now=True` bug on joining date) | `TeacherProfile` (OneToOne with `User`) | Fixed date bug; employee codes, qualification, and subject specialization added. |
| **Fees & Invoicing** | Flat un-audited `Payment` | Full `fees` App (Heads, Structures, Invoices, Receipts) | Enterprise double-entry financial ledger active. Legacy payment table untouched. |

---

## 3. Database Safety & Migration Execution Protocol

### Step 1: Pre-Migration Snapshot & Health Check
Before applying any schema modifications in staging or production:
```bash
# Verify system integrity
python manage.py check --deploy

# PostgreSQL Snapshot
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME -F c -b -v -f "primesoul_pre_migration_$(date +%Y%m%d_%H%M%S).dump"

# SQLite Snapshot (development)
cp db.sqlite3 "db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)"
```

### Step 2: Sequential Migration Application
Migrations must run in dependency order without using `--fake`:
```bash
python manage.py migrate tenants
python manage.py migrate accounts
python manage.py migrate academics
python manage.py migrate students
python manage.py migrate teachers
python manage.py migrate fees
python manage.py migrate
```

### Step 3: Seed Roles and Tenant Defaults
```bash
python manage.py shell -c "from django_school_management.core.roles import ensure_system_roles_exist; ensure_system_roles_exist()"
```

### Step 4: Verification Suite
```bash
python manage.py test tests --verbosity=1
```
Criterion: All 52 tests must pass with 0 failures and 0 errors.

---

## 4. Rollback & Disaster Recovery Strategy

1. **Granular App Rollback**:
   Because all migrations are standard additive Django migrations, any newly applied migration can be safely reverted:
   ```bash
   python manage.py migrate <app_name> <previous_migration_name>
   ```
2. **Database Snapshot Restore**:
   If unrecoverable state divergence occurs during staging testing:
   ```bash
   pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -v --clean "primesoul_pre_migration_<timestamp>.dump"
   ```
3. **Data Integrity Guarantee**:
   All fee structures, invoices, payment transactions, and receipts generated during Phase 3 remain completely isolated and unaffected by Phase 4 architectural cleanup.
