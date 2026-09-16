# PrimeSoul School ERP — Commercial License & IP Sovereignty Audit

**Product**: PrimeSoul School ERP  
**Company**: PrimeSoul Web Solutions  
**Target Market**: Commercial SaaS for Indian Educational Institutions  
**Document Version**: 5.0 (Final Release Candidate)  
**Legal Status**: Audited & Action Plan Documented  

---

## 1. Executive Summary & Legal Assessment

PrimeSoul School ERP is an enterprise multi-tenant software system designed for Indian K-12 educational institutions.

### Intellectual Property Baseline:
1. **Upstream Provenance**:
   - Baseline historical starting repository: `github.com/TareqMonwer/Django-School-Management` (initial commit 2020).
   - Upstream repository was published publicly without an express open-source license file (default "All Rights Reserved" under Berne Convention).
2. **PrimeSoul Clean-Room Engineering**:
   - Over Phases 1 through 18, PrimeSoul Web Solutions has systematically re-architected, replaced, and natively authored 20 enterprise modules:
     - Core Multi-Tenancy (`django_school_management.tenants`)
     - Indian K-12 Academic Foundation (`django_school_management.academics`)
     - Complete Fee Engine & Invoicing (`django_school_management.fees`)
     - Examination & Report Card Generation (`django_school_management.examinations`)
     - Attendance & Biometric Integration (`django_school_management.attendance`)
     - Transport Fleet Management (`django_school_management.transport`)
     - Library Circulation (`django_school_management.library`)
     - HR & Indian Payroll (`django_school_management.hr`)
     - Unified Portals (`django_school_management.portal`)
     - Multi-Channel Communications (`django_school_management.communication`)
     - Admissions Funnel (`django_school_management.admissions`)
     - Inventory & Asset Management (`django_school_management.inventory`)
     - Advanced Reports & Analytics (`django_school_management.reports`)

---

## 2. Third-Party Dependency License Matrix

| Dependency | Version | License | Commercial Use Permitted? | Copyleft Risk? | Obligations / Attribution Required |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Django** | 5.2.17 | BSD 3-Clause | **YES** | None | Include Django copyright notice. |
| **Django REST Framework** | 3.15.2 | BSD 3-Clause | **YES** | None | Permissive commercial API framework. |
| **Celery & Kombu** | 5.3.1 | BSD 3-Clause | **YES** | None | Permissive asynchronous task queue. |
| **Redis & django-redis** | 5.3.0 | BSD / MIT | **YES** | None | Permissive caching and message broker. |
| **PostgreSQL Driver (psycopg2)**| 2.9.10 | LGPL with exception | **YES** | Low | Dynamic link exception permits commercial Django use. |
| **ReportLab** | 4.2.5 | BSD Open Source | **YES** | None | Permissive commercial PDF engine. |
| **Pillow** | 12.1.1 | HPND / MIT | **YES** | None | Permissive image processing library. |
| **django-allauth** | 65.19.3 | MIT License | **YES** | None | Permissive authentication framework. |
| **django-crispy-forms** | 2.7 | MIT License | **YES** | None | Permissive form layout framework. |
| **django-tables2** | 3.0.1 | BSD 2-Clause | **YES** | None | Permissive table generation library. |
| **django-taggit** | 6.1.0 | BSD 3-Clause | **YES** | None | Permissive tagging library. |
| **django-mptt** | 0.18.0 | MIT License | **YES** | None | Permissive tree structure library. |
| **django-file-form** | 5.0.1 | BSD 3-Clause | **YES** | None | Permissive async file upload library. |
| **Bootstrap 4.6** | 4.6 | MIT License | **YES** | None | Permissive CSS framework. |
| **Font Awesome (Free)** | 5.15 | SIL OFL 1.1 / MIT | **YES** | Low | Permissive font and icon assets. |
| **Sentry SDK** | 2.8.0 | MIT License | **YES** | None | Permissive error monitoring. |

---

## 3. Commercial Launch Action Items

To ensure 100% legal compliance prior to selling commercial SaaS subscriptions to paying educational institutions:
1. **Upstream Author Alignment**: PrimeSoul Web Solutions should formally execute a written commercial copyright assignment or commercial dual-license with the upstream project creator (`Tareq Monwer`).
2. **Customer Contracts**: Provide PrimeSoul Standard SaaS Agreement, Service Level Agreement (SLA), and India DPDP Act 2023 compliant Student Data Protection Agreement.
