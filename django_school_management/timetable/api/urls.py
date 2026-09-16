from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkingDayViewSet, TimeSlotViewSet, ClassroomViewSet,
    TimetableEntryViewSet, TimetableConflictValidationAPIView,
    TimetableGenerateAPIView, TimetableCloneAPIView, TimetableClearAPIView
)

router = DefaultRouter()
router.register(r'working-days', WorkingDayViewSet, basename='working-day')
router.register(r'time-slots', TimeSlotViewSet, basename='time-slot')
router.register(r'rooms', ClassroomViewSet, basename='room')
router.register(r'entries', TimetableEntryViewSet, basename='entry')

urlpatterns = [
    path('validate/', TimetableConflictValidationAPIView.as_view(), name='validate'),
    path('generate/', TimetableGenerateAPIView.as_view(), name='generate'),
    path('clone/', TimetableCloneAPIView.as_view(), name='clone'),
    path('clear/', TimetableClearAPIView.as_view(), name='clear'),
    path('', include(router.urls)),
]
