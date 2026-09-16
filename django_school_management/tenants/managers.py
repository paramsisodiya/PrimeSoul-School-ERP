"""
Tenant-aware querysets and managers for PrimeSoul School ERP.
Ensures that queries executed on TenantModel subclasses are automatically filtered by active school.
"""
from django.db import models
from .context import get_current_school


class TenantQuerySet(models.QuerySet):
    """
    QuerySet that automatically scopes queries to the active school tenant.
    """
    def for_school(self, school):
        if school:
            return self.filter(school=school)
        return self.none()

    def for_current_school(self):
        current_school = get_current_school()
        if current_school:
            return self.filter(school=current_school)
        return self.all()


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Default manager for TenantModel.
    When a tenant context is active (e.g., during web requests),
    queries are automatically scoped to that tenant.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        current_school = get_current_school()
        if current_school is not None:
            return qs.filter(school=current_school)
        return qs
