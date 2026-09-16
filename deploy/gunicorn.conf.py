"""
PrimeSoul School ERP - Production Gunicorn Configuration
Optimized for multi-tenant Python WSGI workloads behind Nginx.
"""
import multiprocessing
import os

# Server Socket
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
backlog = 2048

# Worker Processes & Concurrency
# Formula: (2 x num_cores) + 1 for standard I/O bound web workloads
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", 2))
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))  # 120s for heavy ReportLab PDF generation
keepalive = 5

# Memory Leak Prevention & Recycling
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))
graceful_timeout = 30

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
