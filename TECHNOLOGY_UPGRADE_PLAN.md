# PrimeSoul School ERP — Technology Stack Audit & Upgrade Plan

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Educational Institutions  
**Date**: September 2026  
**Status**: Technical Roadmap Reference  

---

## 1. Executive Summary & Stack Evaluation

This document outlines the current state of all primary runtime components, frameworks, third-party libraries, and frontend dependencies in **PrimeSoul School ERP**, together with a phased, safe upgrade roadmap for production deployment.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PrimeSoul Technology Ecosystem                    │
├────────────────────────────────┬───────────────────────────────────────┤
│ Backend Framework              │ Django 4.2.29 LTS (Python 3.11+)       │
│ REST API Layer                 │ Django REST Framework 3.15.2          │
│ Database Engine                │ PostgreSQL 15 / 16 (SQLite in dev)    │
│ Cache & Message Broker         │ Redis 7.x                             │
│ Asynchronous Task Queue        │ Celery 5.3.1                          │
│ PDF Generation Engine          │ ReportLab 4.2.5                       │
│ Frontend Framework             │ Bootstrap 4.6 / Adminator / Tailwind   │
│ Client-side Libraries          │ jQuery 3.4.1 / Select2 / Chart.js     │
│ Monitoring & Telemetry         │ Prometheus + Grafana + Sentry         │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. Component-by-Component Audit

### 2.1 Backend Runtime & Core Framework

| Component | Current Version | Health / Status | Upgrade Recommendation | Target Version |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | `3.11.x` | **EXCELLENT** | Supported through October 2027. High performance, stable typing. | Python 3.11 / 3.12 |
| **Django** | `4.2.29 LTS` | **STABLE / ATTENTION NEEDED** | Django 4.2 extended support ends **April 2026**. Must plan migration to **Django 5.2 LTS** prior to production commercial launch. | Django 5.2 LTS |
| **PostgreSQL** | `15 / 16` (`psycopg2-binary 2.9.10`) | **EXCELLENT** | Fully compatible with all native constraints and JSONB fields. Plan eventual shift to `psycopg3` (`psycopg[binary]`). | PostgreSQL 16+ |
| **Django REST Framework** | `3.15.2` | **EXCELLENT** | Modern, active release supporting Django 4.2 and Django 5.x. | DRF 3.15+ |
| **Celery** | `5.3.1` | **GOOD** | Stable async queue for emails and report generation. | Celery 5.4+ |
| **Redis** | `4.5.0+` (`django-redis 5.4.0`) | **EXCELLENT** | Fast in-memory caching and message broker. | Redis 7.2+ |
| **ReportLab** | `4.2.5` | **EXCELLENT** | Active modern release used for thermal receipts and invoices. High performance. | ReportLab 4.2+ |

---

## 3. Evaluation of Django 4.2 LTS to Django 5.2 LTS Upgrade

### 3.1 Why Upgrade Before Commercial Launch?
- **Support Lifecycle**: Django 4.2 reached general availability in April 2023; its Extended Support phase terminates in **April 2026**. Deploying a new commercial ERP product on an end-of-life framework introduces compliance liabilities and unpatched security vulnerabilities.
- **Django 5.2 LTS**: Delivers long-term security patches until **April 2028**, native generated model fields (`db_default`), enhanced form rendering templates, simplified asynchronous view handling, and optimized database connection pooling.

### 3.2 Compatibility Assessment & Breaking Changes
1. **Third-Party App Compatibility**:
   - `django-allauth 0.54.0`: Fully supports Django 5.x.
   - `django-tables2 2.6.0`: Supports Django 5.x.
   - `drf-yasg 1.21.7`: Requires verification with Django 5.x (or migration to `drf-spectacular`).
   - `django-file-form 3.5.2`: Requires testing against Django 5.0 form rendering changes.
   - `django-mptt 0.14.0`: Stable.
2. **Deprecated APIs to Address**:
   - `USE_L10N` setting is completely removed in Django 5.0.
   - `django.utils.timezone.utc` alias replaced by `datetime.timezone.utc`.
   - Form field error rendering changes.

### 3.3 Recommended Django Upgrade Roadmap (Phase 5 Staging)
- **Step 1**: Audit test suite with Python deprecation warnings enabled:
  ```bash
  python -Wd manage.py test tests
  ```
- **Step 2**: Create isolated branch `upgrade/django-5.2-lts`.
- **Step 3**: Update `requirements.txt` to `Django>=5.2.0,<5.3.0`.
- **Step 4**: Run test suite and resolve any third-party compatibility issues.
- **Step 5**: Validate PostgreSQL staging database migrations.

---

## 4. Frontend Dependencies & UI Modernization

### 4.1 Current Frontend Inventory
- **Bootstrap**: Currently running legacy `Bootstrap 4.6` with `crispy-bootstrap4`.
  - *Risk*: Bootstrap 4 is deprecated and no longer receives active feature development.
  - *Strategy*: Retain during Phase 4 (to preserve working Fees UI and Adminator dashboard), and systematically modernize to modern **Bootstrap 5.3** or **Tailwind CSS** during the Phase 5 visual redesign.
- **jQuery**: Currently includes `jquery-3.4.1.min.js`.
  - *Risk*: Older 3.4.x releases have known CVEs (prototype pollution).
  - *Strategy*: Upgrade bundled vendor file to `jquery-3.7.1.min.js` immediately, with long-term goal of replacing jQuery scripts with modern vanilla ES6 modules.
- **WYSIWYG Editors**:
  - `django-ckeditor 6.6.1` (CKEditor 4): CKEditor 4 reached End of Life in 2023.
  - `django-tinymce 4.1.0`: Modern TinyMCE 6 is already installed and supported.
  - *Strategy*: Standardize entirely on TinyMCE 6 for rich-text circulars and notices, deprecating CKEditor 4.
- **Select2**: `select2@4.1.0-beta.1` CDN link.
  - *Strategy*: Vendor the Select2 CSS/JS locally inside `static/vendor/` to eliminate external CDN latency and availability dependencies.

---

## 5. Summary of Actions by Phase

| Phase | Upgrade Scope | Risk Level | Validation Criteria |
| :--- | :--- | :--- | :--- |
| **Phase 4 (Current)** | Audit, inventory, documentation, and non-breaking vendor updates. | Low | 52/52 tests passing, clean `manage.py check`. |
| **Phase 5 (Staging)** | Django 5.2 LTS test branch, replace CKEditor with TinyMCE, vendor CDN assets. | Medium | Complete automated test suite passing on Django 5.2 + PostgreSQL. |
| **Phase 6 (Pre-Prod)** | Bootstrap 5 UI modernization, eliminate jQuery, replace `drf-yasg` with `drf-spectacular`. | Medium | Visual regression testing, cross-browser responsiveness. |
