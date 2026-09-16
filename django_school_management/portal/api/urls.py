"""
PrimeSoul Unified Portal - REST API Routing
"""
from django.urls import path
from . import views

urlpatterns = [
    # Parent API
    path('parent/dashboard/', views.ParentDashboardAPIView.as_view(), name='api_parent_dashboard'),
    path('parent/children/', views.ParentChildrenAPIView.as_view(), name='api_parent_children'),
    path('parent/children/<int:pk>/', views.ParentChildDetailAPIView.as_view(), name='api_parent_child_detail'),
    path('parent/attendance/', views.ParentAttendanceAPIView.as_view(), name='api_parent_attendance'),
    path('parent/fees/', views.ParentFeesAPIView.as_view(), name='api_parent_fees'),
    path('parent/results/', views.ParentResultsAPIView.as_view(), name='api_parent_results'),
    path('parent/timetable/', views.ParentTimetableAPIView.as_view(), name='api_parent_timetable'),
    path('parent/transport/', views.ParentTransportAPIView.as_view(), name='api_parent_transport'),
    path('parent/library/', views.ParentLibraryAPIView.as_view(), name='api_parent_library'),
    path('parent/notices/', views.ParentNoticesAPIView.as_view(), name='api_parent_notices'),

    # Student API
    path('student/dashboard/', views.StudentDashboardAPIView.as_view(), name='api_student_dashboard'),
    path('student/profile/', views.StudentProfileAPIView.as_view(), name='api_student_profile'),
    path('student/attendance/', views.StudentAttendanceAPIView.as_view(), name='api_student_attendance'),
    path('student/fees/', views.StudentFeesAPIView.as_view(), name='api_student_fees'),
    path('student/results/', views.StudentResultsAPIView.as_view(), name='api_student_results'),
    path('student/timetable/', views.StudentTimetableAPIView.as_view(), name='api_student_timetable'),
    path('student/transport/', views.StudentTransportAPIView.as_view(), name='api_student_transport'),
    path('student/library/', views.StudentLibraryAPIView.as_view(), name='api_student_library'),
    path('student/notices/', views.StudentNoticesAPIView.as_view(), name='api_student_notices'),

    # Teacher API
    path('teacher/dashboard/', views.TeacherDashboardAPIView.as_view(), name='api_teacher_dashboard'),
    path('teacher/timetable/', views.TeacherTimetableAPIView.as_view(), name='api_teacher_timetable'),
    path('teacher/classes/', views.TeacherClassesAPIView.as_view(), name='api_teacher_classes'),
    path('teacher/students/', views.TeacherStudentsAPIView.as_view(), name='api_teacher_students'),
    path('teacher/attendance/', views.TeacherAttendanceAPIView.as_view(), name='api_teacher_attendance'),
    path('teacher/leave/', views.TeacherLeaveAPIView.as_view(), name='api_teacher_leave'),
    path('teacher/payslips/', views.TeacherPayslipsAPIView.as_view(), name='api_teacher_payslips'),
    path('teacher/notices/', views.TeacherNoticesAPIView.as_view(), name='api_teacher_notices'),
]
