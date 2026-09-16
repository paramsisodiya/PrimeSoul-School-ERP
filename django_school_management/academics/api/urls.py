from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AcademicYearViewSet, GradeLevelViewSet, SectionViewSet,
    SubjectViewSet, SubjectAssignmentViewSet, StudentEnrollmentViewSet,
    PromotionExecuteAPIView, AcademicDashboardSummaryAPIView
)

router = DefaultRouter()
router.register(r'years', AcademicYearViewSet, basename='academic-year')
router.register(r'classes', GradeLevelViewSet, basename='grade-level')
router.register(r'sections', SectionViewSet, basename='section')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'assignments', SubjectAssignmentViewSet, basename='subject-assignment')
router.register(r'enrollments', StudentEnrollmentViewSet, basename='student-enrollment')

app_name = 'academics_api'

urlpatterns = [
    path('promotions/execute/', PromotionExecuteAPIView.as_view(), name='promotion_execute'),
    path('dashboard/summary/', AcademicDashboardSummaryAPIView.as_view(), name='dashboard_summary'),
    path('', include(router.urls)),
]
