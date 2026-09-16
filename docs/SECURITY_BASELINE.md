# PrimeSoul School ERP — Security Baseline & Compliance Reference

**Product**: PrimeSoul School ERP  
**Owner**: PrimeSoul Web Solutions  
**Target Market**: Indian K-12 Educational Institutions  
**Document Version**: 4.0  
**Status**: Authoritative Security Specification  

---

## 1. Security Architecture Overview

PrimeSoul School ERP enforces a defense-in-depth security model designed to safeguard sensitive institutional, student, and financial data in a multi-tenant cloud environment.

```
Incoming Request
       │
       ▼
[ WAF & TLS 1.3 Termination ]
       │
       ▼
[ Django Security & CSRF Middleware ]
       │
       ▼
[ WhiteNoise / Static Security ]
       │
       ▼
[ AuthenticationMiddleware (Session / JWT) ]
       │
       ▼
[ TenantMiddleware (Tenant Scoping & Cross-Tenant Guard) ]
       │
       ▼
[ Core RBAC Decorators (@role_required) ]
       │
       ▼
[ TenantManager ORM Scoping (school_id Isolation) ]
       │
       ▼
[ Audited Database / Mutation Execution ]
```

---

## 2. Core Security Controls & Invariants

### 2.1 Multi-Tenant Data Isolation
- **Tenant Scoping**: All institutional data models inherit from `TenantModel`, which introduces an indexed `school_id` foreign key.
- **ORM Isolation**: `TenantManager` and `TenantQuerySet` automatically filter queries by the active request school bound in thread-local storage (`request.tenant`).
- **Cross-Tenant Attack Mitigation**: If an authenticated non-superuser belonging to School A attempts to access School B via host header manipulation or URL parameter tampering, `TenantMiddleware` immediately aborts the transaction with `HTTP 403 Forbidden`.
- **Thread-Local Hygiene**: Thread-local references are explicitly purged in `process_response` and `process_exception` to prevent cross-request leakage across thread pools.

### 2.2 Role-Based Access Control (RBAC)
- **12 Standardized Personas**: Access is strictly governed by the canonical `Role` enum in `django_school_management.core.roles`.
- **View-Level Authorization**: Protected administrative and financial views require the `@role_required` decorator, which verifies both role group membership and tenant alignment before executing view logic.
- **Principle of Least Privilege**: Sensitive financial operations (creating fee structures, waiving fees, voiding invoices) are restricted to `PLATFORM_SUPER_ADMIN`, `SCHOOL_ADMIN`, `PRINCIPAL`, and `ACCOUNTANT`.

### 2.3 Cryptographically Verified Webhooks
- **Elimination of GET State Mutations**: Upstream vulnerable patterns where payment success was marked merely by visiting a callback redirect have been completely neutralized.
- **Cryptographic Signature Verification**:
  - **Stripe**: Verified using `stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)` with tolerance window checks.
  - **Razorpay / SSLCommerz IPN**: Validated via HMAC-SHA256 digest comparison before mutating invoice or payment transaction statuses.
- **Replay Protection**: Incoming webhook IDs are checked against existing `PaymentTransaction.transaction_id` records. Duplicate deliveries are safely acknowledged with `HTTP 200` without re-crediting the student.

### 2.4 CSRF & HTTP Method Protection
- **Strict POST-Only Mutations**: Destructive actions (e.g., deleting faculty, approving fee concessions, generating bulk invoices, cancelling transactions) are strictly prohibited via HTTP `GET`. Any attempt to execute mutations via GET returns `HTTP 405 Method Not Allowed`.
- **CSRF Token Enforcement**: All standard HTML forms and Ajax mutations require valid CSRF tokens (`CsrfViewMiddleware`).
- **SameSite Cookie Policies**: Session cookies are configured with `SameSite='Lax'` or `'Strict'` and `HttpOnly=True`.

### 2.5 PII & Sensitive Data Protection
- **Indian Statutory Identifiers**: Student Aadhaar numbers, Permanent Education Numbers (PEN), and APAAR IDs are stored with strict access controls.
- **Audit Trails**: Access to student identity records and financial adjustments is logged via `core.audit.log_audit_event`.
- **Password Security**: Managed by Django’s PBKDF2 with SHA-256 password hashing. Passwords are never stored in plaintext or logged.
- **Payment Card Data (PCI-DSS Compliance)**: PrimeSoul never captures or stores credit/debit card numbers, CVVs, or bank net banking credentials. All card handling is offloaded to PCI-DSS Level 1 certified gateways.

---

## 3. Infrastructure & Network Baseline

1. **Security Headers**:
   - `X-Frame-Options: DENY` (prevents clickjacking).
   - `X-Content-Type-Options: nosniff` (prevents MIME sniffing).
   - `Strict-Transport-Security` (HSTS enabled in production).
   - `Referrer-Policy: strict-origin-when-cross-origin`.
2. **Health & Monitoring**:
   - `/health/` endpoint verifies database and cache operational status without leaking system metadata.
   - Prometheus metrics (`django_prometheus`) are isolated to administrative network tiers.
3. **Audit Logging**:
   - Centralized logger (`primesoul.audit`) tracks authentication anomalies, role assignments, financial transactions, and privilege escalation.
