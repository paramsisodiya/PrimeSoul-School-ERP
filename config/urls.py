from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from django_school_management.institute.models import InstituteProfile
from django_school_management.accounts.views import dashboard
from django_school_management.core.views import health_check, readiness_check
from django_school_management.examinations.views import public_result_verification_view
from django_school_management.api.urls import schema_view

admin.site.site_header = 'PrimeSoul School ERP Administration'
admin.site.site_title = 'PrimeSoul Site Admin'
admin.site.index_title = 'PrimeSoul School ERP Administration'

DJANGO_ADMIN_URL = settings.DJANGO_ADMIN_URL + '/'
urlpatterns = [
    # Health checks for load balancers, container probes & monitoring
    path('health/', health_check, name='health_check'),
    path('health/ready/', readiness_check, name='readiness_check'),
    # API Documentation (Swagger UI & ReDoc)
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-ui'),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc-ui'),
    # Prometheus metrics (no auth; protect in production via network/firewall)
    path('', include('django_prometheus.urls')),
    # admin_honeypot doesn't support Django 4
    # path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path(DJANGO_ADMIN_URL, admin.site.urls),
    path('', include('django_school_management.pages.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/', include('django_school_management.api.urls')),
    path('dashboard/', dashboard, name='index_view'),
    path('accounts/', include('allauth.urls')),
    path('blog/', include('django_school_management.articles.urls')),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('account/', include('django_school_management.accounts.urls')),
    path('academics/', include('django_school_management.academics.urls')),
    path('notices/', include('django_school_management.notices.site_urls')),
    path('notices/dashboard/', include('django_school_management.notices.dashboard_urls')),
    path('students/', include('django_school_management.students.urls')),
    path('tinymce/', include('tinymce.urls')),
    path('teachers/', include('django_school_management.teachers.urls')),
    path('result/', include('django_school_management.result.urls')),
    path('institute/', include('django_school_management.institute.urls')),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='account/password/password_reset.html'
        ),
        name="password_reset",
    ),
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='account/password/password_reset_done.html'
        ),
        name="password_reset_done",
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='account/password/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='account/password/password-reset-complete.html'
        ),
        name='password_reset_complete'
    ),
    path('dashboard/payments/', include('django_school_management.payments.urls')),
    path('fees/', include('django_school_management.fees.urls', namespace='fees')),
    path('attendance/', include('django_school_management.attendance.urls', namespace='attendance')),
    path('examinations/', include('django_school_management.examinations.urls', namespace='examinations')),
    path('timetable/', include('django_school_management.timetable.urls', namespace='timetable')),
    path('transport/', include('django_school_management.transport.urls', namespace='transport')),
    path('library/', include('django_school_management.library.urls', namespace='library')),
    path('hr/', include('django_school_management.hr.urls', namespace='hr')),
    path('portal/', include('django_school_management.portal.urls', namespace='portal')),
    path('communication/', include('django_school_management.communication.urls', namespace='communication')),
    path('admissions/', include('django_school_management.admissions.urls', namespace='admissions')),
    path('inventory/', include('django_school_management.inventory.urls', namespace='inventory')),
    path('reports/', include('django_school_management.reports.urls', namespace='reports')),
    path('verify/result/<str:verification_code>/', public_result_verification_view, name='verify_result'),
    # API URLS
    path('api/v1/fees/', include('django_school_management.fees.api.urls')),
    path('api/v1/attendance/', include('django_school_management.attendance.api.urls')),
    path('api/v1/examinations/', include('django_school_management.examinations.api.urls')),
    path('api/v1/timetable/', include('django_school_management.timetable.api.urls')),
    path('api/v1/transport/', include('django_school_management.transport.api.urls')),
    path('api/v1/library/', include('django_school_management.library.api.urls')),
    path('api/v1/hr/', include('django_school_management.hr.api.urls')),
    path('api/v1/portal/', include('django_school_management.portal.api.urls')),
    path('api/v1/communication/', include('django_school_management.communication.api.urls')),
    path('api/v1/admissions/', include('django_school_management.admissions.api.urls')),
    path('api/', include('django_school_management.articles.api.routes')),
    path('upload/', include('django_file_form.urls')),
]

from django.urls import re_path
from django.views.static import serve

# Explicitly serve MEDIA_URL across all runtime environments (local and container)
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        serve,
        {'document_root': settings.MEDIA_ROOT}
    ),
]
urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT
)

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls))
    ] + urlpatterns
