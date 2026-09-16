"""
PrimeSoul Core - Base Domain Models
Abstract base models and managers providing automatic multi-tenant scoping and audit timestamps.
"""
from django.db import models
from django_school_management.tenants.models import TenantModel, School
from django_school_management.tenants.managers import TenantManager, TenantQuerySet

# TimeStampedTenantModel provides explicit semantic naming for entities with audit timestamps
TimeStampedTenantModel = TenantModel

__all__ = [
    'TenantModel',
    'TenantManager',
    'TenantQuerySet',
    'TimeStampedTenantModel',
    'School',
]
