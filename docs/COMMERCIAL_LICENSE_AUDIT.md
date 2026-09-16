# PrimeSoul School ERP — Commercial License & IP Audit

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Commercial SaaS for Indian Educational Institutions  
**Date**: September 2026  
**Document Version**: 4.0  
**Status**: Legal & Intellectual Property Baseline  

---

## 1. Executive Summary & Legal Reality Assessment

> [!WARNING]
> **Commercial Use Status: CONDITIONAL / ACTION REQUIRED PRIOR TO SALE**  
> PrimeSoul Web Solutions cannot legally claim unencumbered proprietary commercial ownership of the inherited upstream code without fulfilling specific intellectual property (IP) requirements. The upstream GitHub repository (`TareqMonwer/Django-School-Management`) was published without an explicit open-source license (such as MIT or Apache 2.0).

Under international copyright law (Berne Convention) and GitHub's Terms of Service:
1. **Absence of License = All Rights Reserved**: In the absence of an express license file, the original author retains exclusive copyrights to their original authored work.
2. **GitHub ToS Scope**: Public GitHub repositories implicitly grant users the right to fork, clone, and view code on GitHub; they do **not** convey commercial distribution rights or patent grants.
3. **PrimeSoul Strategy**: To make **PrimeSoul School ERP** completely safe for commercial monetization, PrimeSoul Web Solutions must either:
   - Obtain an express commercial grant or dual-licensing agreement from the original author, or
   - Systematically replace/re-architect remaining upstream legacy components (views, legacy models, templates) with clean-room PrimeSoul proprietary implementations before formal enterprise launch.

---

## 2. Upstream Repository Audit

| Attribute | Upstream Reality | Impact on PrimeSoul ERP | Action Required |
| :--- | :--- | :--- | :--- |
| **Repository** | `github.com/TareqMonwer/Django-School-Management` | Baseline starting codebase | Track provenance and commit history. |
| **Root License File** | **None present** (`LICENSE`, `LICENSE.txt`, `COPYING` are absent) | "All Rights Reserved" default by author | Contact author for written commercial waiver, or replace remaining legacy code. |
| **Commit History** | 100+ commits initialized in 2020 | Public repository on GitHub | Safe for development and internal transformation. |
| **Attribution in Files** | Scattered copyright comments in legacy files | Attribution must be preserved during transition | Retain author comments on legacy code; do not scrub copyright notices. |

---

## 3. Third-Party Dependency Licenses Audit

All third-party libraries installed via `requirements.txt` have been audited for commercial use, sub-licensing, and copyleft (GPL) risks:

| Package | License | Commercial Use Permitted? | Copyleft / Virality Risk? | Notes / Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **Django** | BSD 3-Clause | **YES** | None | Permissive. Requires inclusion of Django copyright notice. |
| **Django REST Framework** | BSD 3-Clause | **YES** | None | Permissive. Standard commercial API framework. |
| **Celery & Kombu** | BSD 3-Clause | **YES** | None | Permissive. |
| **redis & django-redis**| BSD 3-Clause / MIT | **YES** | None | Permissive. |
| **ReportLab** | BSD License (Open Source) | **YES** | None | Standard ReportLab Open Source license allows commercial PDF generation. |
| **Pillow** | HPND / Historical MIT | **YES** | None | Permissive image manipulation library. |
| **psycopg2-binary** | LGPL with exception | **YES** | Low | Dynamic link exception allows commercial Django backend usage. |
| **django-allauth** | MIT License | **YES** | None | Permissive authentication framework. |
| **django-crispy-forms**| MIT License | **YES** | None | Permissive form layout engine. |
| **django-tables2** | BSD 2-Clause | **YES** | None | Permissive HTML table generator. |
| **Bootstrap 4.6** | MIT License | **YES** | None | Permissive CSS framework. |
| **jQuery 3.x** | MIT License | **YES** | None | Permissive JavaScript library. |
| **Font Awesome (Free)**| SIL OFL 1.1 / MIT / CC BY 4.0 | **YES** | Low | Free icons permitted commercially with basic attribution. |
| **Adminator Dashboard**| Colorlib License / CC BY 3.0 | **CONDITIONAL** | Medium | Free use requires backlink attribution in footer. Removal of backlink requires commercial license purchase from Colorlib. |
| **CKEditor 4** | LGPL 2.1 / MPL / GPL | **ATTENTION** | Medium | CKEditor 4 reached EOL; planned replacement with TinyMCE 6 (LGPL/Commercial). |

---

## 4. Components Requiring Replacement Before Commercial Launch

To achieve 100% intellectual property sovereignty and zero copyright liability, the following components are scheduled for complete replacement prior to the first paying customer deployment:

1. **Adminator UI Template Suite (`static/`, `templates/dashboard.html`)**:
   - *Issue*: Inherited from Colorlib's Adminator template under CC BY 3.0 (requires backlink or paid developer license).
   - *Resolution*: Complete the visual redesign in Phase 5 using an independent, custom PrimeSoul Design System built on Tailwind CSS or Bootstrap 5.
2. **Legacy Bangladesh Models & Data Dumps**:
   - *Issue*: `dump.json`, `datadump_pretty.json`, and polytechnic fixtures.
   - *Resolution*: Delete demo dumps and replace with clean, validated Indian K-12 demo seeders.
3. **Legacy Views in `pages`, `articles`, and `payments`**:
   - *Issue*: Authored upstream without explicit licensing.
   - *Resolution*: Phase 5 replaces these with newly authored `communication` and `examinations` modules natively built by PrimeSoul Web Solutions.
4. **Colorlib / UIdeck Footers**:
   - *Issue*: Commented-out UIdeck/Colorlib attribution lines in `website_base.html`.
   - *Resolution*: Scrubbed in Phase 4; landing page rebuilt as a native school portal in Phase 5.

---

## 5. Formal Legal Checklist for PrimeSoul Web Solutions

- [x] Complete inventory of all dependencies and open-source licenses.
- [x] Verify zero AGPL v3 (Affero General Public License) dependencies in backend.
- [x] Replace customer-facing branding with PrimeSoul School ERP trademarks.
- [ ] Execute formal IP assignment / clean-room rewrite of remaining upstream legacy views.
- [ ] Purchase Colorlib commercial developer license (if retaining Adminator assets) OR replace UI shell entirely in Phase 5 redesign.
- [ ] Draft End User License Agreement (EULA) and SaaS Terms of Service for Indian schools.
- [ ] Formulate Student Data Privacy Policy compliant with India's Digital Personal Data Protection (DPDP) Act 2023.
