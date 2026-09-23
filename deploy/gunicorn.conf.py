"""
PrimeSoul School ERP - Production Gunicorn Configuration
Optimized for 512MB RAM container environments (Render, Cloud PaaS, Docker).
"""
import os

# Server Socket
port = os.getenv("PORT", "8000")
bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{port}")
backlog = 1024

# Worker Processes & Concurrency
# In 512 MB memory environments, use 2 workers with 3 threads each (gthread).
# Total memory footprint is ~150-200 MB, leaving ample headroom for database queries and buffers.
workers = int(os.getenv("GUNICORN_WORKERS", 2))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", 3))
worker_connections = 500
timeout = int(os.getenv("GUNICORN_TIMEOUT", 60))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 2))

# Preload Application
# Preloading loads the Django application once in the master process before forking.
# Linux Copy-on-Write (COW) shares base memory pages across workers, reducing RAM by 30-50%.
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() in ("true", "1", "yes")

# Memory Leak Prevention & Worker Recycling
# Periodically restarts worker processes after serving N requests to prevent memory fragmentation.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 500))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

# Process Naming & Security
proc_name = "primesoul_erp_gunicorn"
user = os.getenv("GUNICORN_USER", None)
group = os.getenv("GUNICORN_GROUP", None)

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s µs'

# SSL (if terminating at Gunicorn directly instead of Nginx)
keyfile = os.getenv("GUNICORN_SSL_KEY", None)
certfile = os.getenv("GUNICORN_SSL_CERT", None)

