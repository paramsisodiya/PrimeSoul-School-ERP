"""
PrimeSoul School ERP - Phase 17: Advanced Reports & Analytics URLs
"""
from django.urls import path
from django_school_management.reports import views

app_name = 'reports'

urlpatterns = [
    # Master Executive Dashboard
    path('', views.executive_dashboard, name='dashboard'),

    # Domain Reports
    path('finance/', views.finance_reports, name='finance_reports'),
    path('academics/', views.academic_reports, name='academic_reports'),
    path('attendance/', views.attendance_reports, name='attendance_reports'),
    path('examinations/', views.examination_reports, name='examination_reports'),
    path('admissions/', views.admissions_reports, name='admissions_reports'),
    path('transport/', views.transport_reports, name='transport_reports'),
    path('library/', views.library_reports, name='library_reports'),
    path('hr/', views.hr_reports, name='hr_reports'),
    path('inventory/', views.inventory_reports, name='inventory_reports'),
]
