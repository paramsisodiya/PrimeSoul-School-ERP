"""
PrimeSoul Unified Portal - URL Configuration
"""
from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    # Role-aware entry point
    path('', views.portal_root_redirect, name='portal_root'),

    # Parent Portal
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/children/', views.parent_children, name='parent_children'),
    path('parent/children/<int:student_id>/', views.parent_child_detail, name='parent_child_detail'),
    path('parent/switch/<int:student_id>/', views.parent_child_switch, name='parent_child_switch'),
    path('parent/attendance/', views.parent_attendance, name='parent_attendance'),
    path('parent/fees/', views.parent_fees, name='parent_fees'),
    path('parent/results/', views.parent_results, name='parent_results'),
    path('parent/timetable/', views.parent_timetable, name='parent_timetable'),
    path('parent/transport/', views.parent_transport, name='parent_transport'),
    path('parent/library/', views.parent_library, name='parent_library'),
    path('parent/notices/', views.portal_notices, name='parent_notices'),
    path('parent/profile/', views.parent_profile, name='parent_profile'),

    # Student Portal
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/profile/', views.student_profile, name='student_profile'),
    path('student/attendance/', views.student_attendance, name='student_attendance'),
    path('student/fees/', views.student_fees, name='student_fees'),
    path('student/results/', views.student_results, name='student_results'),
    path('student/timetable/', views.student_timetable, name='student_timetable'),
    path('student/transport/', views.student_transport, name='student_transport'),
    path('student/library/', views.student_library, name='student_library'),
    path('student/notices/', views.portal_notices, name='student_notices'),

    # Teacher Portal
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/profile/', views.teacher_profile, name='teacher_profile'),
    path('teacher/timetable/', views.teacher_timetable, name='teacher_timetable'),
    path('teacher/classes/', views.teacher_classes, name='teacher_classes'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/attendance/', views.teacher_attendance, name='teacher_attendance'),
    path('teacher/attendance/mark/<int:section_id>/', views.teacher_attendance_mark, name='teacher_attendance_mark'),
    path('teacher/exams/', views.teacher_exams, name='teacher_exams'),
    path('teacher/leave/', views.teacher_leave, name='teacher_leave'),
    path('teacher/leave/apply/', views.teacher_leave_apply, name='teacher_leave_apply'),
    path('teacher/payslips/', views.teacher_payslips, name='teacher_payslips'),
    path('teacher/library/', views.teacher_library, name='teacher_library'),
    path('teacher/notices/', views.portal_notices, name='teacher_notices'),

    # Shared Portal Routes
    path('notices/', views.portal_notices, name='notices'),
    path('notices/<int:pk>/', views.portal_notice_detail, name='notice_detail'),
    path('profile/', views.portal_profile, name='profile'),
]
