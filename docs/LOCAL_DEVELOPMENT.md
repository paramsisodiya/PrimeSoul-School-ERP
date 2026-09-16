# PrimeSoul School ERP — Local Development Guide

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Platform**: Windows (PowerShell)  
**Supported Python**: Python 3.11+  
**Target Environment**: Local Continuous Development & Testing  

---

## 1. Prerequisites & Environment Check

PrimeSoul School ERP requires Python 3.11+ and Git on Windows.

> [!IMPORTANT]
> Verify your Python version before proceeding. If Python is not installed or not in PATH, download the official Python 3.11 installer from [python.org](https://www.python.org/downloads/) and ensure **"Add python.exe to PATH"** is selected during installation.

In PowerShell, verify Python installation:
```powershell
python --version
# Expected: Python 3.11.x
```

---

## 2. Virtual Environment Setup

Create and activate an isolated virtual environment in the project directory:

```powershell
# Navigate to the repository root
cd c:\Users\PC\Downloads\Django-School-Management

# Create virtual environment (if not already created)
python -m venv venv

# Set execution policy for the current session (if required by PowerShell)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

Once activated, your prompt will show `(venv)`.

---

## 3. Dependency Installation

Install all required packages from `requirements.txt`:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment Variables Configuration

PrimeSoul ERP utilizes Django settings with sensible local development defaults. For local development, create a `.env` file in the project root if customized credentials or third-party test keys are needed:

```powershell
# Create .env file for local development
@"
DEBUG=True
SECRET_KEY=primesoul-local-dev-secret-key-change-in-production-!@#$
IS_DEMO_ENV=True
DATABASE_URL=sqlite:///db.sqlite3
TIME_ZONE=Asia/Kolkata
ALLOWED_HOSTS=127.0.0.1,localhost
"@ | Out-File -Encoding utf8 .env
```

> [!NOTE]
> Do NOT commit production secrets to Git. The repository includes `.gitignore` to prevent committing `.env` and `db.sqlite3`.

---

## 5. Database Setup & Migrations

Run database migrations to ensure all database tables are up-to-date:

```powershell
python manage.py migrate
```

---

## 6. Seed Demo Data (Idempotent)

PrimeSoul ERP includes an automated, idempotent demo seeder that sets up:
- **Tenant School**: `Delhi Public School, R.K. Puram` (Code: `DPS-1034`, CBSE)
- **Academic Session**: `2026-2027` (April 1, 2026 – March 31, 2027)
- **Class Structure**: Nursery to Class 12 (Sections A & B)
- **Verified Demo Personas**: School Admin, Principal, Accountant, Receptionist, Teacher, Parent, Student
- **Indian Fee Structures**: Class 10 (₹48,000/yr), Class 9 (₹44,000/yr), Class 8 (₹36,000/yr)
- **Student Assignments & Installments**: 5 sample students with quarterly installment schedules
- **Live Transactions & Invoices**: Paid, partial, and pending invoices with generated receipts and QR payloads

To run the seeder:
```powershell
python manage.py seed_demo_school
```

> [!TIP]
> This command is **100% idempotent**. It safely checks existing records and will never duplicate schools, students, fee structures, installments, or invoices if run repeatedly.

---

## 7. Starting the Local Development Server

Launch the Django development server:

```powershell
python manage.py runserver
```

The application will be accessible at:
- **Web ERP Dashboard**: [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- **Sign In**: [http://127.0.0.1:8000/account/auth/login/](http://127.0.0.1:8000/account/auth/login/)
- **Financial Center**: [http://127.0.0.1:8000/fees/dashboard/](http://127.0.0.1:8000/fees/dashboard/)
- **API Documentation**: [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)
- **Liveness Health Check**: [http://127.0.0.1:8000/health/](http://127.0.0.1:8000/health/)

---

## 8. Health Check Verification

Verify database and cache connectivity:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/"
# Output:
# status   database cache
# ------   -------- -----
# ok       ok       ok
```

---

## 9. Running the Automated Test Suite

Run all automated unit and integration tests across multi-tenancy, RBAC, and fees:

```powershell
python manage.py test tests --verbosity=1
# Target: Ran 52 tests ... OK
```

---

## 10. Static Assets Collection

Compile and collect all static assets for production readiness verification:

```powershell
python manage.py collectstatic --noinput
```

---

## 11. Quick Troubleshooting

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'django'` | Virtual environment not activated | Run `.\venv\Scripts\Activate.ps1` |
| `Permission denied` on script execution | PowerShell script execution restriction | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `Health check fails database` | Unapplied migrations | Run `python manage.py migrate` |
| `Access denied / 403 Forbidden` | User role lacks permission for view | Refer to `docs/DEMO_ACCOUNTS.md` for permitted role URLs |
