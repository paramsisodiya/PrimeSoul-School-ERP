from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_dashboard, name='dashboard'),
    path('mark/', views.mark_daily_attendance, name='mark_daily'),
    path('history/', views.attendance_history, name='history'),
    path('students/', views.student_attendance_view, name='student_profile'),
    path('students/<int:student_id>/', views.student_attendance_view, name='student_attendance'),
    path('monthly/', views.monthly_attendance_summary_view, name='monthly_summary'),
    path('low-attendance/', views.low_attendance_alerts_view, name='low_attendance'),
    path('pending/', views.pending_attendance_view, name='pending'),
    path('correct/<int:record_id>/', views.correct_attendance_view, name='correct_record'),
    
    # CSV Exports
    path('export/daily-csv/', views.export_daily_csv, name='export_daily_csv'),
    path('export/monthly-csv/', views.export_monthly_csv, name='export_monthly_csv'),
    path('export/low-attendance-csv/', views.export_low_attendance_csv, name='export_low_attendance_csv'),
]
