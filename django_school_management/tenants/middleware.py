"""
Multi-tenancy middleware for PrimeSoul School ERP.
Resolves and binds the active School tenant to the request and thread-local context.
Enforces cross-tenant data isolation and role boundaries.
"""
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import School, Domain
from .context import set_current_school, clear_current_school


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that determines the active School tenant for every HTTP request.
    
    Resolution Priority:
    1. Authenticated User's explicitly assigned school
    2. Subdomain routing (e.g. `dps.primesoul.in` -> subdomain 'dps')
    3. Custom Domain routing (e.g. `dpsschool.org`)
    4. Explicit Development / API Headers (X-Tenant-Slug, X-Tenant-ID) or query param (?tenant=slug)
    """

    def process_request(self, request):
        host = request.get_host().split(':')[0].lower()
        school = None

        # 1. Header / Parameter resolution (for API clients, mobile apps, dev testing)
        tenant_slug = request.headers.get('X-Tenant-Slug') or request.GET.get('tenant')
        tenant_id = request.headers.get('X-Tenant-ID')

        if tenant_id and tenant_id.isdigit():
            school = School.objects.filter(id=int(tenant_id), is_active=True).first()
        elif tenant_slug:
            school = School.objects.filter(slug=tenant_slug, is_active=True).first()

        # 2. Domain / Subdomain resolution if not yet resolved
        if not school:
            # Check custom domain first
            domain_obj = Domain.objects.filter(domain=host, is_verified=True).select_related('school').first()
            if domain_obj:
                school = domain_obj.school if domain_obj.school.is_active else None
            elif host.endswith('.primesoul.in') or host.endswith('.localhost') or host.endswith('.local'):
                # Extract subdomain prefix
                parts = host.split('.')
                if len(parts) >= 2:
                    subdomain = parts[0]
                    school = School.objects.filter(subdomain=subdomain, is_active=True).first()

        # 3. Authenticated user's school context
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            user_school = getattr(user, 'school', None)
            is_platform_admin = (
                getattr(user, 'is_superuser', False) or
                getattr(user, 'requested_role', None) == 'PLATFORM_SUPER_ADMIN' or
                (hasattr(user, 'has_perm') and user.has_perm('accounts.platform_super_admin'))
            )

            if user_school:
                # If a specific school was resolved via domain/header, check for cross-tenant breach
                if school and school != user_school and not is_platform_admin:
                    if request.path.startswith('/api/'):
                        return JsonResponse(
                            {"detail": "Access Denied: You do not belong to this school tenant."},
                            status=403
                        )
                    return HttpResponseForbidden("Access Denied: Cross-tenant access is prohibited.")
                # Default to user's school if none was resolved from domain
                if not school:
                    school = user_school
            elif is_platform_admin and not school:
                # Platform Super Admin can operate globally or set tenant dynamically
                pass

        # Check tenant activity status
        if school and not school.is_active:
            if request.path.startswith('/api/'):
                return JsonResponse({"detail": "This school account is currently suspended or inactive."}, status=403)
            return HttpResponseForbidden("This school tenant is currently inactive. Please contact support.")

        # Bind active tenant to request and thread-locals
        request.tenant = school
        request.school = school
        set_current_school(school)
        return None

    def process_response(self, request, response):
        clear_current_school()
        return response

    def process_exception(self, request, exception):
        clear_current_school()
        return None
