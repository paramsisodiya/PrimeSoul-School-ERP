# PrimeSoul School ERP — Environment Variables & Configuration Reference

**Product**: PrimeSoul School ERP  
**Company**: PrimeSoul Web Solutions  
**Document Version**: 5.0  

---

## 1. Overview

PrimeSoul School ERP strictly adheres to **Twelve-Factor App** principles for configuration. All secrets, infrastructure connections, and operational credentials are dynamically injected via environment variables.

---

## 2. Configuration Variables Matrix

| Category | Variable | Required in Prod? | Default Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Core** | `DEBUG` | **YES** | `False` | Must be `False` in production. |
| **Core** | `SECRET_KEY` | **YES** | *None* | Unique 50+ character cryptographic secret. |
| **Core** | `ALLOWED_HOSTS` | **YES** | `primesoul.edu.in` | Comma-separated list of valid domain hosts. |
| **Core** | `CSRF_TRUSTED_ORIGINS` | **YES** | `https://primesoul.edu.in` | Origins allowed to make state-modifying requests. |
| **Core** | `DJANGO_ADMIN_URL` | Optional | `admin` | Custom obfuscated path for Django admin interface. |
| **Database** | `DATABASE_URL` | Recommended | *None* | Full PostgreSQL connection string with SSL and pooling. |
| **Database** | `DB_NAME` | Alternative | `primesoul_erp` | PostgreSQL database name. |
| **Database** | `DB_USER` | Alternative | `postgres` | PostgreSQL database user. |
| **Database** | `DB_PASSWORD` | Alternative | *None* | PostgreSQL database password. |
| **Database** | `DB_HOST` | Alternative | `localhost` | PostgreSQL host. |
| **Database** | `DB_PORT` | Alternative | `5432` | PostgreSQL port. |
| **Database** | `CONN_MAX_AGE` | Optional | `600` | Database connection persistent lifetime in seconds. |
| **Redis** | `REDIS_HOST` | **YES** | `localhost` | Redis server hostname for cache and Celery broker. |
| **Redis** | `REDIS_PORT` | **YES** | `6379` | Redis server port. |
| **Celery** | `CELERY_BROKER_URL` | **YES** | `redis://localhost:6379/1` | Redis URL for Celery message queue. |
| **Celery** | `CELERY_RESULT_BACKEND` | Optional | `redis://localhost:6379/2` | Redis URL for Celery result storage. |
| **Security** | `SECURE_SSL_REDIRECT` | **YES** | `True` | Enforces HTTP to HTTPS redirection. |
| **Security** | `SESSION_COOKIE_SECURE` | **YES** | `True` | Restricts session cookies to HTTPS connections. |
| **Security** | `CSRF_COOKIE_SECURE` | **YES** | `True` | Restricts CSRF cookies to HTTPS connections. |
| **Email** | `EMAIL_HOST` | **YES** | `smtp.gmail.com` | Outgoing SMTP server hostname. |
| **Email** | `EMAIL_PORT` | **YES** | `587` | SMTP server port. |
| **Email** | `EMAIL_HOST_USER` | **YES** | *None* | SMTP username or API key. |
| **Email** | `EMAIL_HOST_PASSWORD` | **YES** | *None* | SMTP password. |
| **SMS** | `SMS_PROVIDER` | Optional | `mock` | SMS gateway provider (`msg91`, `textlocal`, `twilio`). |
| **SMS** | `SMS_AUTH_KEY` | Conditional | *None* | Gateway API Key. |
| **SMS** | `SMS_SENDER_ID` | Conditional | `PRSOUL` | 6-character DLT approved Sender ID. |
| **SMS** | `SMS_DLT_ENTITY_ID` | Conditional | *None* | Indian DLT Entity / Principal Registration ID. |
| **WhatsApp** | `WHATSAPP_PROVIDER` | Optional | `mock` | Provider (`meta_cloud`, `gupshup`, `twilio`). |
| **WhatsApp** | `WHATSAPP_API_KEY` | Conditional | *None* | Meta Cloud API access token. |
| **Payments** | `RAZORPAY_KEY_ID` | Conditional | *None* | Razorpay API Key ID. |
| **Payments** | `RAZORPAY_KEY_SECRET` | Conditional | *None* | Razorpay API Secret. |
| **Payments** | `RAZORPAY_WEBHOOK_SECRET` | Conditional | *None* | Razorpay webhook verification signature. |
| **Monitoring** | `USE_SENTRY` | Optional | `False` | Enables Sentry application error tracing. |
| **Monitoring** | `SENTRY_DSN` | Conditional | *None* | Sentry project DSN. |

---

## 3. Secret Rotation Procedure

1. Generate new API secret or cryptographic key.
2. Update the variable in `/var/www/primesoul/envs/.env`.
3. Gracefully reload Gunicorn workers:
   ```bash
   sudo systemctl reload primesoul-gunicorn
   ```
4. Restart Celery background workers:
   ```bash
   sudo systemctl restart primesoul-celery
   ```
