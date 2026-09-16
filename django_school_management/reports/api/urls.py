"""
PrimeSoul School ERP - Phase 17: Reports REST API URLs
"""
from django.urls import path
from django_school_management.reports.api import views

app_name = 'reports_api'

urlpatterns = [
    path('dashboard/', views.ExecutiveDashboardAPIView.as_view(), name='dashboard'),
    path('finance/', views.FinanceReportsAPIView.as_view(), name='finance'),
    path('hr/', views.HRReportsAPIView.as_view(), name='hr'),
    path('academics/', views.AcademicsReportsAPIView.as_view(), name='academics'),
    path('attendance/', views.AttendanceReportsAPIView.as_view(), name='attendance'),
    path('examinations/', views.ExaminationReportsAPIView.as_view(), name='examinations'),
    path('admissions/', views.AdmissionsReportsAPIView.as_view(), name='admissions'),
    path('transport/', views.TransportReportsAPIView.as_view(), name='transport'),
    path('library/', views.LibraryReportsAPIView.as_view(), name='library'),
    path('inventory/', views.InventoryReportsAPIView.as_view(), name='inventory'),
]
