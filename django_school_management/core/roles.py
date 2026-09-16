"""
PrimeSoul Core - RBAC Roles & Group Management
Central registry for all 12 system personas, role assignment, and validation.
"""
from django_school_management.accounts.roles import (
    Role,
    ensure_system_roles_exist,
    assign_role_to_user,
    user_has_role,
)

__all__ = [
    'Role',
    'ensure_system_roles_exist',
    'assign_role_to_user',
    'user_has_role',
]
