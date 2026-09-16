from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AdmissionSessionViewSet, AdmissionClassConfigViewSet,
    AdmissionEnquiryViewSet, AdmissionApplicationViewSet,
    AdmissionDocumentViewSet, AdmissionInterviewViewSet,
    AdmissionAssessmentViewSet, AdmissionDashboardAPIView,
    PublicAdmissionApplyAPIView, PublicAdmissionStatusAPIView
)

router = DefaultRouter()
router.register(r'sessions', AdmissionSessionViewSet, basename='admission-session')
router.register(r'classes', AdmissionClassConfigViewSet, basename='admission-class-config')
router.register(r'enquiries', AdmissionEnquiryViewSet, basename='admission-enquiry')
router.register(r'applications', AdmissionApplicationViewSet, basename='admission-application')
router.register(r'documents', AdmissionDocumentViewSet, basename='admission-document')
router.register(r'interviews', AdmissionInterviewViewSet, basename='admission-interview')
router.register(r'assessments', AdmissionAssessmentViewSet, basename='admission-assessment')

urlpatterns = [
    path('dashboard/', AdmissionDashboardAPIView.as_view(), name='admission-dashboard'),
    path('public/apply/', PublicAdmissionApplyAPIView.as_view(), name='public-admission-apply'),
    path('public/status/', PublicAdmissionStatusAPIView.as_view(), name='public-admission-status'),
    path('', include(router.urls)),
]
