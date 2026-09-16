from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AttendanceRecordViewSet, BulkMarkAttendanceAPIView,
    AttendanceCorrectionAPIView, TodayAttendanceSummaryAPIView,
    StudentAttendanceAPIView, PendingAttendanceAPIView
)

router = DefaultRouter()
router.register(r'', AttendanceRecordViewSet, basename='attendance-record')

urlpatterns = [
    path('bulk-mark/', BulkMarkAttendanceAPIView.as_view(), name='attendance-bulk-mark'),
    path('<int:pk>/correct/', AttendanceCorrectionAPIView.as_view(), name='attendance-correct'),
    path('today/', TodayAttendanceSummaryAPIView.as_view(), name='attendance-today-summary'),
    path('summary/', TodayAttendanceSummaryAPIView.as_view(), name='attendance-summary'),
    path('student/<int:pk>/', StudentAttendanceAPIView.as_view(), name='attendance-student-summary'),
    path('pending/', PendingAttendanceAPIView.as_view(), name='attendance-pending'),
    path('', include(router.urls)),
]
