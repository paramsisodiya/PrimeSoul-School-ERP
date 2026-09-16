# PrimeSoul School ERP — Data & Model Migration Plan

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Schools  
**Document Version**: 2.0 (P0 Foundation)  
**Status**: Active  

---

## 1. Migration Overview & Guiding Principles

The transformation of the legacy single-institution codebase into **PrimeSoul School ERP (Multi-Tenant SaaS)** requires a zero-data-loss, reversible migration strategy.

### Core Principles:
1. **Zero Data Loss**: Existing database records must remain intact.
2. **Backward Compatibility**: Legacy foreign keys and model structures are retained as nullable references during the transition period.
3. **No Fake Migrations**: Migrations must be clean, deterministic, and execute sequentially without `--fake` flags.
4. **Gradual Deprecation**: Bangladesh-specific polytechnic models are isolated, marked as `[LEGACY]`, and preserved in database tables until formal phase-out.

---

## 2. Legacy Model vs. PrimeSoul SaaS Model Mapping

| Domain Area | Legacy Model | PrimeSoul Model | Migration Strategy / Status |
| :--- | :--- | :--- | :--- |
| **Tenancy** | `InstituteProfile` (singleton with `active=True` constraint) | `School`, `Domain`, `Subscription` | New `tenants` app. `User.school` and `TenantModel` establish tenant boundaries. Legacy `institute` FK preserved as nullable. |
| **Authentication & RBAC** | `User.requested_role` (string check `"admin"`) | `User.school` + `Role` enum + Django `Group` RBAC | Standardized 12 system roles. Added helper methods `require_school_access` and `@role_required`. |
| **Academic Session** | `AcademicSession` (year-based polytechnic term) | `AcademicYear` | New model supporting April 1 – March 31 Indian sessions with unique current session per school constraint. |
| **Academic Structure** | `Department` & `Semester` (1st–8th polytechnic terms) | `GradeLevel`, `Section`, `AcademicStream` | Native K-12 progression (Nursery–12th), sections (A, B, C), and 11th/12th streams. Legacy models retained with tenant-scoped constraints. |
| **Student** | `AdmissionStudent` (SSC/HSC/Dakhil/BDT) | `Student` (K-12 Indian) | Native fields: Aadhaar, PEN, APAAR ID, Blood Group, Category. Scoped roll number uniqueness: `(school, academic_year, grade_level, section, roll_number)`. |
| **Parents** | Flat string fields on Student | `ParentProfile`, `StudentGuardianRelationship` | Separate parent entities linked to students; supports multiple siblings without duplicating parent records. |
| **Teachers** | `Teacher` (`joining_date auto_now=True`) | `TeacherProfile` (OneToOne with `User`) | Fixed bug where `joining_date` updated on every save. Added employee code, qualification, specialization, and Indian contact fields. |

---

## 3. Deprecated & Bangladesh-Specific Components

The following legacy components have been isolated or refactored:
1. **Payment Flow**:
   - Insecure GET redirect URLs (e.g. `/admission/ssl-success/`) no longer mutate payment status in the database.
   - Replaced with cryptographically signed webhook handlers (`stripe_webhook`, `ssl_ipn_webhook`).
2. **Bangladesh-Specific Fields**:
   - `tribal_status`, `children_of_freedom_fighter`, `ssc_roll`, `ssc_registration`, `dakhil`, and `bdt` currency defaults are marked as legacy.
   - Primary operations now use Indian K-12 identifiers (Aadhaar, PEN, APAAR, INR, Asia/Kolkata).
3. **Destructive GET Endpoints**:
   - Endpoints like `teacher_delete_view` have been refactored to strict `POST` endpoints with CSRF protection and tenant permissions.

---

## 4. Step-by-Step Execution Plan

### Step 1: Pre-Migration Backup
Prior to executing migrations on any production/staging instance, create a full snapshot:
```bash
# PostgreSQL backup
pg_dump -h <host> -U <user> -d <db_name> -F c -b -v -f "primesoul_backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Step 2: Apply Django Migrations
Execute migrations across all apps in order:
```bash
python manage.py makemigrations tenants
python manage.py makemigrations accounts
python manage.py makemigrations academics
python manage.py makemigrations students
python manage.py makemigrations teachers
python manage.py migrate
```

### Step 3: Populate Default Roles & Super Admin
```bash
# Seed standard 12 Django Groups
python manage.py shell -c "from django_school_management.accounts.roles import ensure_system_roles_exist; ensure_system_roles_exist()"
```

### Step 4: System Verification
```bash
python manage.py check --deploy
python manage.py test tests.test_p0_foundation
```

---

## 5. Rollback & Disaster Recovery Strategy

All migrations generated in Phase 2 are standard additive Django migrations:
1. If a migration failure occurs, rollback can be targeted per app:
   ```bash
   python manage.py migrate <app_name> <previous_migration_name>
   ```
2. In the event of a catastrophic deployment failure, restore the PostgreSQL snapshot:
   ```bash
   pg_restore -h <host> -U <user> -d <db_name> -v --clean "primesoul_backup_<timestamp>.dump"
   ```
