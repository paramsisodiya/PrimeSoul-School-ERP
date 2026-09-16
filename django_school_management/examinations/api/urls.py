from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExaminationSessionViewSet, ExamViewSet, ExamSubjectViewSet, GradeScaleViewSet,
    StudentMarkViewSet, StudentExamResultViewSet, BulkMarksAPIView,
    CalculateResultsAPIView, FinalizeResultsAPIView, PublishResultsAPIView,
    LockResultsAPIView, MarksCorrectionAPIView, StudentResultHistoryAPIView,
    ClassResultSummaryAPIView
)

router = DefaultRouter()
router.register(r'sessions', ExaminationSessionViewSet, basename='api-sessions')
router.register(r'exams', ExamViewSet, basename='api-exams')
router.register(r'subjects', ExamSubjectViewSet, basename='api-exam-subjects')
router.register(r'grades', GradeScaleViewSet, basename='api-grade-scales')
router.register(r'marks', StudentMarkViewSet, basename='api-marks')
router.register(r'results', StudentExamResultViewSet, basename='api-results')

urlpatterns = [
    # Router endpoints
    path('', include(router.urls)),

    # Workflow Actions
    path('bulk-marks/', BulkMarksAPIView.as_view(), name='api-bulk-marks'),
    path('correct/', MarksCorrectionAPIView.as_view(), name='api-marks-correct'),
    path('results/<int:exam_id>/calculate/', CalculateResultsAPIView.as_view(), name='api-calculate-results'),
    path('results/<int:exam_id>/finalize/', FinalizeResultsAPIView.as_view(), name='api-finalize-results'),
    path('results/<int:exam_id>/publish/', PublishResultsAPIView.as_view(), name='api-publish-results'),
    path('results/<int:exam_id>/lock/', LockResultsAPIView.as_view(), name='api-lock-results'),

    # Analytics & History
    path('student/<int:student_id>/', StudentResultHistoryAPIView.as_view(), name='api-student-history'),
    path('class-summary/<int:exam_id>/', ClassResultSummaryAPIView.as_view(), name='api-class-summary'),
]
