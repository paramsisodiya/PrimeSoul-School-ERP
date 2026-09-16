# PrimeSoul School ERP — Demo Accounts & Access Matrix

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Environment**: Local Testing & Verification  
**Default Password**: `demo@123` (Uniform password for all seeded demo personas)  

---

## 1. Demo Credentials Matrix

The following accounts are automatically provisioned and verified (`approval_status="a"`) by `python manage.py seed_demo_school`:

| Role Persona | Email / Username | Password | School Tenant | System Access Level |
| :--- | :--- | :--- | :--- | :--- |
| **School Admin** | `admin@primesoul.com`<br>`admin_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Full Administrative Access**<br>Superuser & Staff enabled |
| **Principal** | `principal@primesoul.com`<br>`principal_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Executive Academic Leadership**<br>Academics, Staff, Approvals |
| **Accountant** | `accountant@primesoul.com`<br>`accountant_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Financial Operations**<br>Fees, Invoices, Collections, Receipts |
| **Receptionist** | `receptionist@primesoul.com`<br>`receptionist_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Front Desk & Admissions**<br>Counter Payments, Inquiries |
| **Teacher** | `teacher@primesoul.com`<br>`teacher_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Faculty Portal**<br>Assigned Classes, Student Attendance |
| **Parent** | `parent@primesoul.com`<br>`parent_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Parent Portal**<br>Child Fees, Invoices, Receipts |
| **Student** | `student@primesoul.com`<br>`student_demo` | `demo@123` | Delhi Public School, R.K. Puram | **Student Portal**<br>Personal Fees Dues, Receipts, Profile |

---

## 2. Granular Role Access & Restrictions

### 1. School Admin (`admin@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Full operational overview & KPI statistics
  - `/fees/`: Full financial center, heads, structures, assignments, installments, concessions, invoices, collections, receipts, reports
  - `/students/`: All student rosters, add new student admissions, parent records
  - `/teachers/`: Faculty rosters, teacher additions, staff designations
  - `/academics/`: Academic sessions, grade levels, sections, subjects
  - `/account/`: User accounts management, role assignment, user requests approval
  - `/api/v1/fees/`: Full REST API read/write operations
  - `/health/`: Liveness diagnostics
- **Expected Restricted Areas**:
  - Cross-tenant data of other schools (guarded by `TenantMiddleware` and `School.objects.filter(...)`).

---

### 2. Principal (`principal@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Executive school overview and KPIs
  - `/academics/`: Academic setup, classes, sections, subjects
  - `/students/`: Student lists, admissions overview, parent contacts
  - `/teachers/`: Teacher rosters and staff profiles
  - `/fees/dashboard/`: Financial overview metrics
  - `/fees/concessions/`: **Sole authority** (alongside Admin) to review and **Approve/Reject Scholarship Concessions**
  - `/fees/invoices/`, `/fees/receipts/`: Read-only financial audits
- **Expected Restricted Areas**:
  - Cannot alter tenant billing or subscription plan
  - Cannot edit system settings or database user permissions
  - Cannot execute raw accounting balance overrides

---

### 3. Accountant (`accountant@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Financial dashboard overview
  - `/fees/`: Full daily accounting operations:
    - `/fees/heads/`: Configure fee components
    - `/fees/structures/`: Set class fee structures
    - `/fees/student-fees/`: Assign fee structures & trigger installments
    - `/fees/installments/`: Monitor unpaid/overdue installments
    - `/fees/invoices/`: Issue student invoices
    - `/fees/payments/`: Record offline fee collections (Cash, UPI, Cheque, Bank Transfer)
    - `/fees/receipts/`: View official receipts, trigger PDF downloads, verify QR codes
- **Expected Restricted Areas**:
  - Cannot approve concessions where `approval_required=True` (requires Principal or Admin)
  - Cannot edit teacher designations or academic session dates
  - Cannot alter user account credentials or system roles

---

### 4. Receptionist (`receptionist@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Front desk dashboard
  - `/students/addstudent/`: Register new student inquiries and admission applications
  - `/students/`: Look up student roll numbers, sections, and parent phone numbers
  - `/fees/payments/`: Record counter fee payments from visiting parents
  - `/fees/receipts/`: Print official fee receipts for parents at the counter
  - `/fees/dashboard/`: View daily collection figures
- **Expected Restricted Areas**:
  - Cannot create or modify fee heads or fee structures
  - Cannot grant fee concessions or waivers
  - Cannot cancel invoices or alter accounting balances
  - Cannot access staff designations or system administration

---

### 5. Teacher (`teacher@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Teacher portal view
  - `/teachers/my-portal/`: Teacher profile, assigned class timetable
  - `/academics/`: View grade levels and sections
  - `/students/`: View roster of students in assigned class (Class 10A)
- **Expected Restricted Areas**:
  - **403 Forbidden** on `/fees/` administrative and accounting routes (`/fees/heads/`, `/fees/structures/`, `/fees/invoices/`, `/fees/payments/`)
  - Cannot edit student financial records
  - Cannot access system user management or settings

---

### 6. Parent (`parent@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Parent portal showing enrolled children (Aarav Sharma)
  - View child's fee installment schedule
  - View and download invoices issued to their child
  - View and download official PDF fee receipts
- **Expected Restricted Areas**:
  - **403 Forbidden** on all staff, teacher, and accounting views
  - Cannot view other parents' or unrelated students' records (strictly scoped by student parent relationship)
  - Cannot record offline payments directly (only school cashier/accountant can confirm offline receipts)

---

### 7. Student (`student@primesoul.com`)
- **Allowed Areas**:
  - `/dashboard/`: Student portal showing enrolled class (Class 10A)
  - View personal fee dues, installment dates, and payment history
  - Download official receipt PDFs for verified payments
- **Expected Restricted Areas**:
  - **403 Forbidden** on all faculty, financial management, and school administration pages
  - Cannot view other students' records or school ledger
