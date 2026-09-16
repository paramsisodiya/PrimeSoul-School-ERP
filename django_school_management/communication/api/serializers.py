from rest_framework import serializers
from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, AnnouncementCategory,
    Notification, NotificationPreference, NotificationTemplate, NotificationDeliveryLog
)


class AnnouncementTargetSerializer(serializers.ModelSerializer):
    target_display = serializers.CharField(source='get_target_type_display', read_only=True)

    class Meta:
        model = AnnouncementTarget
        fields = ['id', 'target_type', 'target_display', 'grade_level', 'section', 'student', 'employee']


class AnnouncementSerializer(serializers.ModelSerializer):
    targets = AnnouncementTargetSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = Announcement
        fields = [
            'id', 'school', 'title', 'content', 'category', 'category_name',
            'priority', 'status', 'created_by', 'created_by_name',
            'published_at', 'scheduled_at', 'expires_at', 'attachment',
            'targets', 'created'
        ]
        read_only_fields = ['school', 'created_by', 'created', 'published_at']


class NotificationSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'school', 'recipient_user', 'announcement',
            'title', 'message', 'notification_type', 'priority',
            'channel', 'channel_display', 'status', 'status_display',
            'read_at', 'delivered_at', 'failed_at', 'failure_reason',
            'created'
        ]
        read_only_fields = ['school', 'recipient_user', 'created']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'school', 'user', 'announcement_enabled',
            'email_enabled', 'sms_enabled', 'whatsapp_enabled',
            'attendance_alerts', 'fee_alerts', 'exam_alerts',
            'transport_alerts', 'library_alerts', 'hr_alerts'
        ]
        read_only_fields = ['school', 'user']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'school', 'name', 'code', 'channel', 'subject', 'body', 'active', 'variables']
        read_only_fields = ['school']


class NotificationDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDeliveryLog
        fields = ['id', 'notification', 'channel', 'provider', 'provider_message_id', 'status', 'attempted_at', 'delivered_at', 'failed_at', 'failure_reason']
