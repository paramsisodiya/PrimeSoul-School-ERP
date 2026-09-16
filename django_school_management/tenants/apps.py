from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_school_management.tenants'
    verbose_name = 'Tenants & Multi-Tenancy'
