from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnnouncementViewSet, NotificationViewSet,
    NotificationPreferenceAPIView, NotificationTemplateViewSet,
    NotificationDeliveryLogViewSet, CommunicationDashboardAPIView
)

router = DefaultRouter()
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'delivery-logs', NotificationDeliveryLogViewSet, basename='notification-delivery-log')

urlpatterns = [
    path('dashboard/', CommunicationDashboardAPIView.as_view(), name='communication-dashboard'),
    path('preferences/', NotificationPreferenceAPIView.as_view(), name='notification-preferences'),
    path('', include(router.urls)),
]
