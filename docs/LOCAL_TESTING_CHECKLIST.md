# PrimeSoul School ERP — Local Testing Checklist & Manual Test Runs
**Product:** PrimeSoul School ERP  
**Organization:** PrimeSoul Web Solutions  
**Target Market:** Indian K-12 Schools (CBSE / ICSE / State Boards)  
**Phase:** 4.5 — Local Development & Complete UI Transformation  
**Base URL:** `http://127.0.0.1:8000`

---

## Quick Setup Before Testing

Before running manual tests, ensure the local environment is prepared:

```powershell
# 1. Start Django development server (if not already running)
& "C:\Users\PC\python311\python.exe" manage.py runserver

# 2. Seed / Re-seed demo school idempotently (safe to re-run anytime)
& "C:\Users\PC\python311\python.exe" manage.py seed_demo_school
```

Demo Credentials:
- **Default Password for All Accounts:** `demo@123`

---

## 24-Step Comprehensive Test Matrix

### 1. Login Flow
- **URL:** `http://127.0.0.1:8000/account/login/`
- **Steps:**
  1. Open browser to `/account/login/`.
  2. Notice the modern PrimeSoul brand styling (dark theme, blue accent, logo).
  3. Under "Quick Fill Demo Persona", click the **Admin** button.
  4. Notice the email `admin@primesoul.com` and password `demo@123` auto-fill into the input fields.
  5. Click **Sign In to Dashboard**.
- **Expected Result:**
  - Authenticated successfully and redirected to `/dashboard/`.
  - Top navigation bar shows "Admin User" and role badge "ADMIN".

---

### 2. Dashboard Experience
- **URL:** `http://127.0.0.1:8000/dashboard/`
- **Steps:**
  1. View the main dashboard area.
  2. Verify school identity displayed: **PrimeSoul Public School**.
  3. Verify academic session: **2026-2027**.
  4. Verify KPI Cards: Total Students (5), Total Faculty (1), Total Invoices (3), Collected Amount (₹16,000.00), Outstanding Amount (₹9,000.00).
  5. Verify quick action links to **Collect Fee**, **Create Invoice**, and **Manage Structures**.
  6. Verify recent payments table displays latest transactions with student names and amounts.
- **Expected Result:**
  - Real database metrics display without missing data or broken layouts.
  - Sidebar sections: OVERVIEW, ACADEMICS, STUDENTS, FACULTY, FINANCE, ADMINISTRATION are properly organized.

---

### 3. Admin Persona Test
- **Account:** `admin@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `admin@primesoul.com`.
  2. Navigate through `/fees/`, `/fees/heads/`, `/fees/structures/`, `/fees/invoices/`.
  3. Verify access to all 6 sidebar sections.
  4. Verify access to create, update, and manage fee items.
- **Expected Result:**
  - Full read/write access to all core ERP and financial modules.

---

### 4. Principal Persona Test
- **Account:** `principal@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `principal@primesoul.com`.
  2. Navigate to `/dashboard/`.
  3. Check high-level analytics, fee collection overview, student lists, and academic areas.
  4. View `/fees/` dashboard and summaries.
- **Expected Result:**
  - Comprehensive view of school operations, analytics, and reports.

---

### 5. Accountant Persona Test
- **Account:** `accountant@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `accountant@primesoul.com`.
  2. Check sidebar: Finance section is fully accessible.
  3. Access `/fees/heads/`, `/fees/structures/`, `/fees/invoices/`, `/fees/payments/`, `/fees/receipts/`.
  4. Verify permissions to record payments, approve concessions, and generate receipts.
- **Expected Result:**
  - Full operational access to fees and accounts workflows.

---

### 6. Receptionist Persona Test
- **Account:** `receptionist@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `receptionist@primesoul.com`.
  2. Access fee collection desk at `/fees/invoices/`.
  3. Record counter payments and issue standard fee receipts.
- **Expected Result:**
  - Can collect fees and generate payment receipts; configuration settings (e.g. system administration) are restricted.

---

### 7. Teacher Persona Test
- **Account:** `teacher@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `teacher@primesoul.com`.
  2. View dashboard: Notice teacher-specific information.
  3. Verify that institutional financial administration links are restricted.
- **Expected Result:**
  - Access limited to academic and student classroom interfaces.

---

### 8. Parent Persona Test
- **Account:** `parent@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `parent@primesoul.com`.
  2. Access `/fees/invoices/`.
- **Expected Result:**
  - Only invoices and receipts belonging to their own linked child (e.g. Aarav Sharma) are visible. No access to other students' financial records.

---

### 9. Student Persona Test
- **Account:** `student@primesoul.com` / `demo@123`
- **Steps:**
  1. Log in as `student@primesoul.com`.
  2. Access `/fees/invoices/` and `/fees/receipts/`.
- **Expected Result:**
  - Only their own student fee records and receipts are shown.

---

### 10. Fee Head Management
- **URL:** `http://127.0.0.1:8000/fees/heads/`
- **Steps:**
  1. Log in as Admin or Accountant.
  2. Navigate to **Finance > Fee Heads**.
  3. Verify existing heads: Tuition Fee, Annual Development, Laboratory Fee, Library Fee.
  4. In "Add New Fee Head" form:
     - Name: `Sports & Activity Fee`
     - Code: `SPORTS`
     - Frequency: `ANNUAL`
     - Click **Save Fee Head**.
- **Expected Result:**
  - Fee head is created and visible in the table with modern badge and details.

---

### 11. Fee Structure Configuration
- **URL:** `http://127.0.0.1:8000/fees/structures/`
- **Steps:**
  1. Navigate to **Finance > Fee Structures**.
  2. Verify existing structures (e.g., Grade 10 Standard Fee ₹25,000).
  3. In "Create Structure" form:
     - Name: `Grade 9 General Fee`
     - Academic Year: `2026-2027`
     - Frequency: `QUARTERLY`
     - Total Amount: `20000.00`
     - Click **Save Fee Structure**.
- **Expected Result:**
  - Structure saved and listed in the table with total component calculations.

---

### 12. Student Fee Assignment
- **URL:** `http://127.0.0.1:8000/fees/student-fees/`
- **Steps:**
  1. Navigate to **Finance > Student Fees**.
  2. Select Student: `Vihaan Gupta (STU-00004)`.
  3. Select Fee Structure: `Grade 10 Standard Fee (2026-2027)`.
  4. Click **Assign Structure**.
- **Expected Result:**
  - StudentFeeAssignment record created/updated with `status='ACTIVE'`.
  - Installments generated automatically.

---

### 13. Installment Generation & Inspection
- **URL:** `http://127.0.0.1:8000/fees/installments/`
- **Steps:**
  1. Navigate to **Finance > Installments**.
  2. Filter by status or student name.
  3. Verify quarterly breakdown (Q1, Q2, Q3, Q4) with due dates and amounts.
  4. Verify status badges: `PENDING`, `PARTIAL`, `PAID`, or `OVERDUE`.
- **Expected Result:**
  - 4 installments displayed per assigned student with exact installment sequence.

---

### 14. Invoice Generation (₹10,000 Test Invoice)
- **URL:** `http://127.0.0.1:8000/fees/invoices/`
- **Steps:**
  1. Navigate to **Finance > Invoices**.
  2. In "Generate Invoice" modal/form:
     - Student: `Ananya Patel (STU-00002)`
     - Academic Year: `2026-2027`
     - Due Date: `2026-10-15`
     - Amount: `10000.00`
     - Click **Generate Invoice**.
- **Expected Result:**
  - Invoice created with unique number (e.g., `INV-2026-0004`).
  - Total Amount: `₹10,000.00`, Paid: `₹0.00`, Status: `PENDING` (badge: yellow/amber).

---

### 15. Partial Payment Test (₹4,000 against ₹10,000)
- **URL:** `http://127.0.0.1:8000/fees/payments/`
- **Steps:**
  1. Navigate to **Finance > Payments**.
  2. Click **Record Payment**:
     - Invoice: Select `INV-2026-0004` (Total: ₹10,000.00)
     - Amount: `4000.00`
     - Payment Mode: `UPI`
     - Reference Number: `UPI/TXN/99001`
     - Click **Record Payment**.
- **Expected Result:**
  - Payment recorded successfully.
  - Payment status: `SUCCESS`.
  - Return to `/fees/invoices/` and inspect `INV-2026-0004`:
    - Total: `₹10,000.00`
    - Paid: `₹4,000.00`
    - Balance: `₹6,000.00`
    - Status: `PARTIAL` (badge: cyan/info `badge-status-partial`).

---

### 16. Full Payment Test (Remaining ₹6,000)
- **URL:** `http://127.0.0.1:8000/fees/payments/`
- **Steps:**
  1. In **Finance > Payments**, click **Record Payment**:
     - Invoice: Select `INV-2026-0004`
     - Amount: `6000.00`
     - Payment Mode: `BANK_TRANSFER`
     - Reference Number: `NEFT/AXIS/8821`
     - Click **Record Payment**.
- **Expected Result:**
  - Payment of ₹6,000.00 recorded.
  - Return to `/fees/invoices/` and inspect `INV-2026-0004`:
    - Total: `₹10,000.00`
    - Paid: `₹10,000.00`
    - Balance: `₹0.00`
    - Status: `PAID` (badge: green `badge-status-paid`).

---

### 17. Fee Receipt Generation
- **URL:** `http://127.0.0.1:8000/fees/receipts/`
- **Steps:**
  1. Navigate to **Finance > Receipts**.
  2. Locate the receipts generated for the ₹4,000 and ₹6,000 payments.
  3. Verify receipt numbers (e.g. `REC-2026-0004` and `REC-2026-0005`).
  4. Verify student details, payment method, date, and tenant header.
- **Expected Result:**
  - Clean receipt records with amounts and download actions.

---

### 18. PDF Receipt Generation
- **URL:** `/fees/receipts/<id>/pdf/`
- **Steps:**
  1. On the Receipts list page, click the **PDF** download icon on any receipt.
- **Expected Result:**
  - HTTP 200 response with `Content-Type: application/pdf` or HTML print view.
  - Proper school letterhead: "PrimeSoul Public School", GSTIN/Affiliation, student details, and breakdown.

---

### 19. QR Code Receipt Verification
- **URL:** `/fees/receipts/<id>/`
- **Steps:**
  1. View the receipt details.
  2. Verify QR code is rendered containing verification URL / cryptographic receipt hash.
  3. Scan QR or click verification link.
- **Expected Result:**
  - Verification endpoint confirms the authenticity of the issued receipt.

---

### 20. Cheque Payment Workflow
- **URL:** `http://127.0.0.1:8000/fees/payments/`
- **Steps:**
  1. Record a payment with Payment Mode = `CHEQUE`.
  2. Enter Cheque Number: `CHQ-445566`, Bank: `State Bank of India`.
  3. Initial Status: `PENDING`.
  4. Once cleared, update status to `SUCCESS`.
- **Expected Result:**
  - Cheque clearing flow records properly without double counting pending cheques.

---

### 21. Fee Concession / Scholarship Workflow
- **URL:** `http://127.0.0.1:8000/fees/concessions/`
- **Steps:**
  1. Navigate to **Finance > Concessions**.
  2. Create a concession application:
     - Student: `Diya Sharma (STU-00003)`
     - Concession Type: `MERIT`
     - Discount Type: `PERCENTAGE`
     - Value: `20` (20% fee waiver)
     - Reason: `Academic Excellence Board Topper`
     - Click **Submit Request**.
  3. Log in as Principal or Admin to approve.
- **Expected Result:**
  - Concession is listed with `PENDING` badge, and upon approval transitions to `APPROVED`.

---

### 22. Multi-Tenant Isolation
- **Steps:**
  1. Inspect queries via Django shell or direct DB verification.
  2. Confirm every `School`, `Student`, `FeeHead`, `FeeStructure`, `Invoice`, and `Payment` contains `school_id`.
  3. Query data for School 1; confirm records from School 2 (if any) are never returned in querysets.
- **Expected Result:**
  - 100% tenant isolation maintained across all ORM queries and views.

---

### 23. Unauthorized Access & 403 Page
- **Steps:**
  1. Log out or log in as `student@primesoul.com`.
  2. Attempt to navigate directly to an admin-only endpoint: `http://127.0.0.1:8000/fees/heads/` or configuration URL.
- **Expected Result:**
  - Clean PrimeSoul 403 Forbidden page displayed (`HTTP 403 • Forbidden - Access Restricted`).
  - Contains "Return to Dashboard" button and "Switch Account" link. No raw Django stack trace.

---

### 24. Responsive Mobile UI Inspection
- **Devices/Widths to Test:**
  - Desktop: 1440px
  - Laptop: 1280px
  - Tablet: 768px
  - Mobile: 390px (iPhone 14 / modern Android)
- **Steps:**
  1. Open Developer Tools (`F12`) and toggle Device Toolbar.
  2. Set width to `390px`.
  3. Verify top navigation displays mobile hamburger button (`#sidebarToggle`).
  4. Click the hamburger button:
     - Sidebar slides out smoothly from left as an off-canvas drawer.
     - Dark backdrop overlay appears behind the sidebar.
  5. Tap the backdrop or toggle button:
     - Sidebar slides back and backdrop disappears.
  6. Inspect table views:
     - Horizontal scrolling occurs within table cards (`.table-responsive`), preserving page width without breaking viewport layout.
  7. Check KPI cards on dashboard:
     - Cards wrap into single-column cards with touch-friendly spacing.
- **Expected Result:**
  - Zero horizontal body overflow, touch targets $\ge 44\text{px}$, crisp modern mobile typography.
