# PrimeSoul School ERP

> **A Comprehensive, Multi-Tenant Indian K-12 School Management & ERP SaaS Platform**  
> Developed & Maintained by **PrimeSoul Web Solutions**

---

## Overview

**PrimeSoul School ERP** is an enterprise-grade, multi-tenant School Management System designed specifically for Indian K-12 institutions (CBSE, ICSE, and State Boards). Built on **Django 5.0**, **PostgreSQL**, **Redis**, and **Celery**, it delivers robust academic management, admissions, fee administration with DLT/GST compliance, digital examinations, real-time attendance, HR payroll, transport tracking, library automation, inventory control, and dedicated self-service portals for Students, Parents, Teachers, and Administrators.

---

## Main Modules & Features

| Module | Core Functionality |
|--------|---------------------|
| **Multi-Tenancy & SaaS Core** | Subdomain & header-based tenant isolation, custom school branding, tiered subscription plans, and 12-Role Granular RBAC. |
| **Academics & Structure** | Academic years, terms, grade levels (Classes I–XII), streams (Science, Commerce, Arts), sections, subject mapping, and class teacher assignments. |
| **Admissions & Enrollment** | Online public admission application portal, document verification, application fee collection, merit list generation, and roll number allotment. |
| **Fee Management & Finance** | Multi-head fee structures (Tuition, Transport, Lab), discounts/concessions, online payment gateways (Razorpay/UPI/Cards), partial payments, offline receipts, fee reminders, and GST reporting. |
| **Attendance & Leaves** | Daily session attendance (Morning/Afternoon), RFID/Biometric integration APIs, student & staff leave management, and automated absent SMS/WhatsApp notifications. |
| **Examinations & Grading** | Exam scheduling, room allocation, mark entry workflows, grading scales (CBSE CCE 8-point/9-point, percentage), and automated PDF report card generation. |
| **Timetable & Scheduling** | Class and teacher timetable generation, period scheduling, classroom management, and teacher substitution assignment. |
| **HR, Staff & Payroll** | Employee directory, designation hierarchy, monthly salary structures (Basic, HRA, DA, PF, ESI, TDS), salary slip generation, and payout tracking. |
| **Transport Management** | Bus fleet inventory, route mapping, stop-wise fee assignment, driver details, and student vehicle allocation. |
| **Library Management** | Book cataloging with ISBN/Barcode, member cards, issue/return circulation tracking, overdue fine calculation, and inventory audit. |
| **Inventory & Assets** | Category management, supplier directory, purchase orders, stock ledger, low-stock alerts, and departmental item issuance. |
| **Communication Hub** | Multi-channel communication (Email, DLT-compliant SMS via MSG91/Textlocal, WhatsApp Business API), notice boards, and event broadcasts. |
| **Self-Service Portals** | Dedicated modern web portals for **Students**, **Parents** (fee payment, gradebook), **Teachers** (attendance, marks), and **School Admins**. |
| **Analytics & Reports** | Comprehensive exportable reports (Excel/CSV/PDF) for finance, attendance, academic performance, and staff metrics. |

---

## Technology Stack

- **Backend Framework**: Python 3.11+ / Django 5.0
- **Database**: PostgreSQL 14+ with Connection Pooling (`psycopg2-binary`)
- **Caching & Message Broker**: Redis 7+
- **Task Queue & Scheduler**: Celery 5.3+ & Celery Beat
- **WSGI Application Server**: Gunicorn (Multi-threaded worker cluster)
- **Web Server & Reverse Proxy**: Nginx with HTTP/2 and SSL termination
- **Static Asset Pipeline**: WhiteNoise with Brotli/Gzip compression and manifest cache-busting
- **Observability**: Prometheus (`/metrics`) and standardized healthchecks (`/health/`)

---

## Local Development Setup

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Git

### 2. Clone the Repository
```bash
git clone https://github.com/your-org/PrimeSoul-School-ERP.git
cd PrimeSoul-School-ERP
```

### 3. Create & Activate Virtual Environment
```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Environment Configuration
Copy `.env.example` to `.env` and configure your database and Redis settings:
```bash
cp .env.example .env
```

### 6. Apply Database Migrations & Initialize Roles
```bash
python manage.py migrate
python manage.py init_production  # Provisions 12 core RBAC system roles
python manage.py createsuperuser  # Create platform superadmin
```

### 7. Optional Demo Data Seeding (Local Development Only)
```bash
python manage.py seed_demo_school
```

### 8. Run Development Server
```bash
python manage.py runserver
```
*Access the application at `http://127.0.0.1:8000/`.*

### 9. Run Celery Worker & Beat (Separate Terminals)
```bash
# Terminal 1: Celery Worker
celery -A config worker -l INFO

# Terminal 2: Celery Beat Scheduler
celery -A config beat -l INFO
```

---

## Environment Variables

See [.env.example](.env.example) and [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for full variable definitions.

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `DJANGO_SETTINGS_MODULE` | Active Django settings module | `config.settings.production` |
| `DEBUG` | Enable debug mode (Must be `False` in prod) | `False` |
| `SECRET_KEY` | Cryptographic secret key (64+ chars) | *Required* |
| `ALLOWED_HOSTS` | Comma-separated domain names | `primesoul.com,*.primesoul.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF validation | `https://primesoul.com,https://*.primesoul.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://user:pass@host:5432/dbname` |
| `REDIS_URL` | Redis cache & broker URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Redis URL for Celery message broker | `redis://localhost:6379/1` |
| `EMAIL_HOST_USER` | SMTP server username | `apikey` |
| `EMAIL_HOST_PASSWORD` | SMTP server password | *Required for email* |
| `SMS_PROVIDER` | SMS gateway provider (`msg91`, `textlocal`) | `msg91` |
| `RAZORPAY_KEY_ID` | Razorpay payment gateway key | *Required for online fees* |

---

## Automated Test Suite

PrimeSoul School ERP comes with a 100% passing automated test suite covering all modules, multi-tenancy, and security layers:

```bash
python manage.py test tests
```

---

## Production Deployment Overview

Production deployment is fully documented in [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) and [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

### Quick Deployment Checklist (Ubuntu 22.04/24.04 LTS)
1. **Server Setup**: Provision Ubuntu Linux host with Python 3.11, PostgreSQL, Redis, and Nginx.
2. **Repository Deployment**: Clone code into `/var/www/primesoul` and create virtualenv.
3. **Environment**: Configure `/etc/primesoul/.env` with production secrets (`chmod 600`).
4. **Database & Assets**:
   ```bash
   python manage.py migrate --settings=config.settings.production
   python manage.py init_production --settings=config.settings.production
   python manage.py collectstatic --noinput --settings=config.settings.production
   ```
5. **Systemd Services**: Install and start `primesoul-gunicorn.service`, `primesoul-celery.service`, and `primesoul-beat.service` from `deploy/systemd/`.
6. **Nginx & SSL**: Enable `deploy/nginx/primesoul.conf` and obtain Let's Encrypt certificates via `certbot`.

---

## License & Commercial Rights

Copyright &copy; 2026 **PrimeSoul Web Solutions**. All rights reserved.  
Clean commercial distribution license documented in [COMMERCIAL_LICENSE_AUDIT.md](COMMERCIAL_LICENSE_AUDIT.md).