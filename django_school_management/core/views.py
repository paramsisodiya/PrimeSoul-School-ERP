"""
PrimeSoul School ERP - Core Health & Readiness Check Views
Production probes for Nginx, load balancers, and Kubernetes/Docker orchestration.
"""
import time
import logging
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Lightweight Liveness Probe.
    Returns HTTP 200 if Python/Django process is responsive.
    """
    return JsonResponse({
        "status": "healthy",
        "service": "primesoul_school_erp",
        "timestamp": int(time.time()),
    }, status=200)


def readiness_check(request):
    """
    Deep Readiness Probe.
    Checks database connection and cache/Redis availability.
    Returns HTTP 200 if all services are operational, or HTTP 503 if any service fails.
    """
    checks = {
        "database": False,
        "cache": False,
    }
    healthy = True

    # 1. Database Check
    try:
        cursor = connections['default'].cursor()
        cursor.execute("SELECT 1;")
        row = cursor.fetchone()
        if row and row[0] == 1:
            checks["database"] = True
    except Exception as exc:
        logger.error(f"Readiness probe: Database check failed: {exc}")
        healthy = False

    # 2. Cache / Redis Check
    try:
        cache_key = "_readiness_probe_key"
        cache.set(cache_key, "ok", 10)
        val = cache.get(cache_key)
        if val == "ok":
            checks["cache"] = True
    except Exception as exc:
        logger.error(f"Readiness probe: Cache check failed: {exc}")
        healthy = False

    status_code = 200 if healthy else 503
    return JsonResponse({
        "status": "ready" if healthy else "degraded",
        "checks": checks,
        "timestamp": int(time.time()),
    }, status=status_code)
