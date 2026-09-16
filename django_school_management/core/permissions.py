"""
PrimeSoul Core - RBAC & Tenant Scoped Permissions
Decorators and helpers for view-level and API-level authorization.
"""
from django_school_management.accounts.permissions import (
    require_school_access,
    user_has_permission,
    role_required,
)

__all__ = [
    'require_school_access',
    'user_has_permission',
    'role_required',
]
