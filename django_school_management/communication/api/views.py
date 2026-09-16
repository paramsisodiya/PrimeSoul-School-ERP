from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, Notification,
    NotificationPreference, NotificationTemplate, NotificationDeliveryLog
)
from .serializers import (
    AnnouncementSerializer, NotificationSerializer,
    NotificationPreferenceSerializer, NotificationTemplateSerializer,
    NotificationDeliveryLogSerializer
)
from django_school_management.communication.services.notification_service import (
    publish_announcement, mark_notification_as_read, mark_all_notifications_read
)
from django_school_management.communication.selectors.communication_selectors import (
    get_communication_dashboard_metrics, get_user_unread_count
)


def get_request_school(request):
    """Safely resolves school tenant from request."""
    if hasattr(request, 'tenant') and request.tenant:
        return request.tenant
    if hasattr(request, 'school') and request.school:
        return request.school
    if request.user.is_authenticated and getattr(request.user, 'school', None):
        return request.user.school
    from django_school_management.tenants.models import School
    return School.objects.first()


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for tenant announcements.
    """
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return Announcement.objects.filter(school=school).select_related('created_by', 'category').prefetch_related('targets').order_by('-created')

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        announcement = self.get_object()
        notif_count = publish_announcement(announcement, published_by=request.user)
        return Response({
            'status': 'published',
            'announcement_id': announcement.id,
            'notifications_dispatched': notif_count
        })


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read and manage current user's in-app notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return Notification.objects.filter(
            recipient_user=self.request.user,
            school=school
        ).order_by('-created')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        mark_notification_as_read(notification, request.user)
        return Response({'status': 'read', 'notification_id': notification.id})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        school = get_request_school(self.request)
        count = mark_all_notifications_read(request.user, school)
        return Response({'status': 'success', 'marked_read': count})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        school = get_request_school(self.request)
        count = get_user_unread_count(request.user, school)
        return Response({'unread_count': count})


class NotificationPreferenceAPIView(APIView):
    """
    Retrieve or update current user's notification preferences.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = get_request_school(request)
        pref, _ = NotificationPreference.objects.get_or_create(school=school, user=request.user)
        serializer = NotificationPreferenceSerializer(pref)
        return Response(serializer.data)

    def put(self, request):
        school = get_request_school(request)
        pref, _ = NotificationPreference.objects.get_or_create(school=school, user=request.user)
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    Manage notification message templates.
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return NotificationTemplate.objects.filter(school=school)

    def perform_create(self, serializer):
        school = get_request_school(self.request)
        serializer.save(school=school, created_by=self.request.user)


class NotificationDeliveryLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit log of notification dispatches.
    """
    serializer_class = NotificationDeliveryLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        school = get_request_school(self.request)
        return NotificationDeliveryLog.objects.filter(notification__school=school).order_by('-attempted_at')


class CommunicationDashboardAPIView(APIView):
    """
    Aggregated communication metrics for staff.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        school = get_request_school(request)
        metrics = get_communication_dashboard_metrics(school)
        return Response(metrics)
