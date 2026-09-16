"""
Centralized permission and authorization system for PrimeSoul School ERP.
Validates:
1. Authentication
2. Tenant membership (User belongs to requested School)
3. Role / Permission assignment
4. Object ownership / tenant scope
"""
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from .roles import Role, user_has_role


def require_school_access(user, school) -> bool:
    """
    Validates that a user has legitimate access to a specific school tenant.
    Platform Super Admins have global access. All other users must match user.school.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user_has_role(user, Role.PLATFORM_SUPER_ADMIN):
        return True
    user_school = getattr(user, 'school', None)
    return user_school is not None and school is not None and user_school.pk == school.pk


def user_has_permission(user, permission_codename: str) -> bool:
    """
    Validates if user has a specific Django permission or is a SuperAdmin.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user_has_role(user, Role.PLATFORM_SUPER_ADMIN):
        return True
    return user.has_perm(permission_codename)


def role_required(*allowed_roles):
    """
    Decorator for views that requires the user to belong to one of the specified roles.
    Also validates tenant active state and membership.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                if request.path.startswith('/api/'):
                    return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
                return redirect('account_login')

            if user.is_superuser or user_has_role(user, Role.PLATFORM_SUPER_ADMIN):
                return view_func(request, *args, **kwargs)

            # Check tenant alignment
            tenant = getattr(request, 'tenant', None)
            if tenant and not require_school_access(user, tenant):
                if request.path.startswith('/api/'):
                    return JsonResponse({"detail": "Forbidden: You do not have access to this school tenant."}, status=403)
                return HttpResponseForbidden("Forbidden: Cross-tenant access is prohibited.")

            # Check role permissions
            if not user_has_role(user, *allowed_roles):
                if request.path.startswith('/api/'):
                    return JsonResponse({"detail": "Forbidden: Insufficient permissions for this action."}, status=403)
                raise PermissionDenied("You do not have the required role to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# Convenience decorators
platform_super_admin_required = role_required(Role.PLATFORM_SUPER_ADMIN)
school_admin_required = role_required(Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL)
principal_required = role_required(Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.VICE_PRINCIPAL)
academic_staff_required = role_required(
    Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL,
    Role.VICE_PRINCIPAL, Role.ACADEMIC_COORDINATOR, Role.TEACHER
)
teacher_required = role_required(
    Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.TEACHER
)
accountant_required = role_required(
    Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.PRINCIPAL, Role.ACCOUNTANT
)
student_or_parent_required = role_required(
    Role.PLATFORM_SUPER_ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT
)
