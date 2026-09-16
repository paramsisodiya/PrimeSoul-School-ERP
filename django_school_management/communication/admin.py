from django.contrib import admin
from .models import (
    AnnouncementCategory, Announcement, AnnouncementTarget,
    Notification, NotificationPreference, NotificationTemplate, NotificationDeliveryLog
)


class AnnouncementTargetInline(admin.TabularInline):
    model = AnnouncementTarget
    extra = 1


@admin.register(AnnouncementCategory)
class AnnouncementCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'is_active')
    list_filter = ('school', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'priority', 'status', 'published_at', 'created_by')
    list_filter = ('school', 'status', 'priority', 'category')
    search_fields = ('title', 'content')
    inlines = [AnnouncementTargetInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient_user', 'channel', 'status', 'priority', 'delivered_at', 'read_at')
    list_filter = ('school', 'channel', 'status', 'priority', 'notification_type')
    search_fields = ('title', 'message', 'recipient_user__username')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'school', 'email_enabled', 'sms_enabled', 'whatsapp_enabled')
    list_filter = ('school',)
    search_fields = ('user__username',)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'channel', 'active')
    list_filter = ('school', 'channel', 'active')
    search_fields = ('name', 'code')


@admin.register(NotificationDeliveryLog)
class NotificationDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ('notification', 'channel', 'provider', 'status', 'attempted_at', 'delivered_at')
    list_filter = ('channel', 'status', 'provider')
    search_fields = ('provider_message_id', 'failure_reason')
