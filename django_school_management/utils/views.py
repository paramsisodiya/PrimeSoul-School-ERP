"""Views for health check (readiness/liveness)."""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.core.cache import cache


@csrf_exempt
@require_GET
@never_cache
def health_view(request):
    """
    Health check for load balancers and Kubernetes.
    Returns 200 if DB and cache are reachable, 503 otherwise.
    """
    status = "ok"
    code = 200
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = str(e)
        status = "degraded"
        code = 503

    try:
        cache.set("health_check", 1, timeout=5)
        if cache.get("health_check") != 1:
            raise Exception("cache read/write failed")
        checks["cache"] = "ok"
    except Exception as e:
        checks["cache"] = str(e)
        status = "degraded"
        code = 503

    return JsonResponse({"status": status, "checks": checks}, status=code)


def csrf_failure_view(request, reason=""):
    """
    Custom CSRF failure handler for PrimeSoul School ERP.
    Gracefully handles expired, stale, or back-forward-cache CSRF tokens.
    For login/authentication forms, silently refreshes the token and redirects
    with an informative notice rather than crashing to a raw 403 error page.
    """
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.conf import settings
    from django.middleware.csrf import get_token, rotate_token

    path = request.path or ''
    rotate_token(request)
    new_token = get_token(request)
    cookie_name = getattr(settings, 'CSRF_COOKIE_NAME', 'csrftoken')

    # If submitting login or auth form, gracefully redirect back to login
    if any(auth_path in path for auth_path in ['/login/', '/accounts/', '/auth/']):
        messages.warning(request, "Your security session was refreshed. Please enter your credentials to sign in.")
        response = redirect(path if path else '/accounts/login/')
        response.set_cookie(cookie_name, new_token)
        return response

    context = {
        'reason': reason,
        'path': path,
        'new_token': new_token,
    }
    response = render(request, '403_csrf.html', context, status=403)
    response.set_cookie(cookie_name, new_token)
    return response
