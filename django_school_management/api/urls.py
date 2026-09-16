"""
Central API URL config. All routes are under /api/ (see config/urls.py).

Convention: path('v1/<resource>/', include('<app>.api.urls')) defines the resource
path. In each app's api/urls.py, register the main viewset with prefix r'' so
the final URL is /api/v1/<resource>/ (not /api/v1/<resource>/<resource>/).
Sub-resources use a non-empty prefix, e.g. router.register(r'applications', ...).
"""
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# API Documentation
schema_view = get_schema_view(
    openapi.Info(
        title="PrimeSoul School ERP API",
        default_version='v1',
        description="Comprehensive REST API for PrimeSoul School ERP (PrimeSoul Web Solutions)",
        contact=openapi.Contact(email="support@primesoul.in"),
        license=openapi.License(name="Proprietary / PrimeSoul Web Solutions"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # API Documentation
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # API Endpoints
    path('v1/students/', include('django_school_management.students.api.urls')),
    path('v1/academics/', include('django_school_management.academics.api.urls')),
    path('v1/attendance/', include('django_school_management.attendance.api.urls')),
    path('v1/examinations/', include('django_school_management.examinations.api.urls')),
    path('v1/timetable/', include('django_school_management.timetable.api.urls')),
    path('v1/transport/', include('django_school_management.transport.api.urls')),
    path('v1/library/', include('django_school_management.library.api.urls')),
    path('v1/hr/', include('django_school_management.hr.api.urls')),
    path('v1/portal/', include('django_school_management.portal.api.urls')),
    path('v1/communication/', include('django_school_management.communication.api.urls')),
    path('v1/admissions/', include('django_school_management.admissions.api.urls')),
    path('v1/inventory/', include('django_school_management.inventory.api.urls')),
    path('v1/reports/', include('django_school_management.reports.api.urls')),
    path('v1/teachers/', include('django_school_management.teachers.api.urls')),
    path('v1/payments/', include('django_school_management.payments.api.urls')),
    path('v1/articles/', include('django_school_management.articles.api.urls')),
]
