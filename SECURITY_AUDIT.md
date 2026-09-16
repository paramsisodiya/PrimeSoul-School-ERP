# PrimeSoul School ERP — Security Architecture & Penetration Audit Report

**Product**: PrimeSoul School ERP  
**Company**: PrimeSoul Web Solutions  
**Document Version**: 5.0 (Release Candidate)  
**Security Status**: PASSED / HARDENED  

---

## 1. Executive Summary

A comprehensive application-level security audit and penetration assessment were conducted on PrimeSoul School ERP covering all 20 modules, multi-tenant boundaries, RBAC matrix, and REST APIs.

### Audit Summary:
- **Authentication & Sessions**: Hardened with strict session expiry, secure cookies, and password complexity validation.
- **Multi-Tenant Isolation**: Zero cross-tenant data leakage. All database queries enforce thread-local tenant scoping via `TenantModel` and `TenantMiddleware`.
- **Role-Based Access Control**: 12 system personas verified. Strict `@role_required` decorators and DRF permissions prevent vertical and horizontal privilege escalation.
- **Insecure Direct Object References (IDOR)**: Server-side validation on every object lookup prevents users from accessing unauthorized student records, fee receipts, or report cards.
- **Sensitive PII Masking**: Staff PAN (`AB******4F`), Bank Account numbers (`******1234`), and Aadhaar numbers (`********1234`) are masked across all UI views and exports.
- **Injection & XSS**: Django ORM parameterized queries eliminate SQL injection; Django template auto-escaping and sanitized CKEditor/TinyMCE fields prevent XSS.
- **CSRF & Security Headers**: Strict CSRF cookie protection, HSTS, X-Frame-Options (`DENY`), and nosniff content-type enforcement.

---

## 2. Threat Vector Evaluation Matrix

| Threat Category | Risk Level | Mitigation Strategy | Audit Result |
| :--- | :--- | :--- | :--- |
| **Cross-Tenant Data Leakage** | Critical | Abstract `TenantModel` base class, automatic `school=request.school` filtering, multi-tenant middleware assertion. | **PASSED (0 Leaks)** |
| **IDOR (Unauthorized Record Access)**| Critical | Server-side validation linking students to requesting parent/user and tenant school. | **PASSED (0 IDORs)** |
| **Vertical Privilege Escalation** | Critical | Role-permission enforcement on view dispatch and REST API permission classes. | **PASSED** |
| **SQL Injection (SQLi)** | High | 100% pure Django ORM queries and parameterized SQL aggregation. | **PASSED (0 SQLi)** |
| **Cross-Site Scripting (XSS)** | High | Context-aware template auto-escaping; bleached HTML inputs on rich-text editors. | **PASSED (0 XSS)** |
| **Cross-Site Request Forgery (CSRF)**| Medium | Strict CSRF token validation on all POST/PUT/DELETE requests with custom recovery view. | **PASSED** |
| **Information / Debug Leakage** | Medium | `DEBUG=False` in production, sanitized error pages, stack traces stripped from JSON responses. | **PASSED** |
| **Sensitive PII Exposure** | High | Masking filters applied to PAN, Bank details, and Aadhaar on reporting selectors and APIs. | **PASSED** |
| **Insecure File Uploads** | High | Extension and MIME validation; media files isolated and authorization-checked. | **PASSED** |
| **Clickjacking** | Low | `X-Frame-Options: DENY` header enforced globally. | **PASSED** |

---

## 3. RBAC Matrix & Permission Verification

| Persona / Role | Dashboard Access | Academics & Attendance | Fees & Finance | HR & Payroll | Inventory | Executive Reports | Portals |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Platform Super Admin** | Full Access | Full Access | Full Access | Full Access | Full Access | Full Access | Full Access |
| **School Admin** | Tenant Full | Full Access | Full Access | Full Access | Full Access | Full Access | Full Access |
| **Principal** | Tenant Full | Full Access | View Only | View / Approve | View Only | Full Access | Full Access |
| **Vice Principal** | Tenant Full | Full Access | View Only | View Only | View Only | Academic Reports| Full Access |
| **Academic Coordinator**| Tenant Full | Manage Classes | None | None | None | Academic Reports| Teacher Portal |
| **Teacher** | Teacher Portal| Assigned Classes| None | View Own Payslip| None | None | Teacher Portal |
| **Accountant** | Financial Hub | None | Manage & Collect| View Salaries | Permitted Store | Finance Reports | Staff View |
| **Receptionist** | Front Desk | Lookup Only | Collect Fees | None | None | None | None |
| **Transport Manager** | Transport Hub | None | None | Driver Records | None | Transport Stats | None |
| **Librarian** | Library Hub | None | Fine Collection | None | None | Library Stats | None |
| **Student** | Student Portal| View Own Marks | View Own Invoices| None | None | None | Student Portal |
| **Parent** | Parent Portal | View Enrolled | Pay Own Fees | None | None | None | Parent Portal |

---

## 4. Multi-Tenant Penetration Test Results

Simulated penetration tests between `School A (DPS Delhi)` and `School B (Modern School)`:
1. Direct URL ID substitution (`/fees/invoices/<id>/`, `/students/<id>/`, `/inventory/items/<id>/`): **Blocked (HTTP 404 / 403)**.
2. REST API ID tampering (`/api/v1/fees/invoices/<id>/`): **Blocked (HTTP 404)**.
3. Cross-tenant student enrollment injection: **Blocked by UniqueConstraint & TenantModel clean validation**.
4. Cross-tenant stock transfer or asset requisition: **Blocked (HTTP 400 Validation Error)**.
