"""
PrimeSoul Core - Tenant & School Context Scoping
Provides reliable thread-local scoping and request tenant binding for multi-tenant isolation.
"""
from django_school_management.tenants.context import (
    set_current_school,
    get_current_school,
    clear_current_school,
    set_current_tenant,
    get_current_tenant,
    clear_current_tenant,
)

__all__ = [
    'set_current_school',
    'get_current_school',
    'clear_current_school',
    'set_current_tenant',
    'get_current_tenant',
    'clear_current_tenant',
]
