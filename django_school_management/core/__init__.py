"""
PrimeSoul School ERP - Core Architecture Module
Centralized infrastructure for tenant scoping, RBAC, audit logging,
domain exceptions, and standardized API conventions.
"""
from .roles import Role
from .context import get_current_tenant, set_current_tenant, get_current_school
from .models import TenantModel, TenantManager, TimeStampedTenantModel
from .exceptions import PrimeSoulERPException, TenantIsolationError

__all__ = [
    'Role',
    'get_current_tenant',
    'set_current_tenant',
    'get_current_school',
    'TenantModel',
    'TenantManager',
    'TimeStampedTenantModel',
    'PrimeSoulERPException',
    'TenantIsolationError',
]
