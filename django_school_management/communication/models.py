from django.db import models
from django.conf import settings
from django.utils import timezone
from model_utils.models import TimeStampedModel
from django_prometheus.models import ExportModelOperationsMixin


class AnnouncementCategory(ExportModelOperationsMixin('announcement_category'), TimeStampedModel):
    """
    Configurable categorization for announcements per school tenant.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='announcement_categories',
        null=True, blank=True
    )
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Announcement Categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code'], name='unique_school_announcement_category_code')
        ]

    def __str__(self):
        return f"{self.name} ({self.school.name if self.school else 'Global'})"


class Announcement(ExportModelOperationsMixin('announcement'), TimeStampedModel):
    """
    Tenant-scoped School Announcement.
    Supports multi-audience targeting and rich scheduling.
    """
    STATUS_DRAFT = 'DRAFT'
    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_ARCHIVED = 'ARCHIVED'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    PRIORITY_LOW = 'LOW'
    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'

    PRIORITY_CHOICES = (
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent / Emergency'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='announcements'
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.ForeignKey(
        AnnouncementCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='announcements'
    )
    category_name = models.CharField(max_length=100, blank=True, default='General')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_announcements'
    )
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to='communication/announcements/', null=True, blank=True)

    class Meta:
        ordering = ['-created_at' if hasattr(TimeStampedModel, 'created_at') else '-created']

    def __str__(self):
        return f"[{self.priority}] {self.title} ({self.get_status_display()})"

    @property
    def is_published(self) -> bool:
        return self.status == self.STATUS_PUBLISHED


class AnnouncementTarget(ExportModelOperationsMixin('announcement_target'), models.Model):
    """
    Target audience mapping for an announcement.
    Supports broad roles or fine-grained specific classrooms/individuals.
    """
    TARGET_ALL = 'ALL_SCHOOL'
    TARGET_PARENTS = 'PARENTS'
    TARGET_STUDENTS = 'STUDENTS'
    TARGET_TEACHERS = 'TEACHERS'
    TARGET_STAFF = 'STAFF'
    TARGET_CLASS = 'SPECIFIC_CLASS'
    TARGET_SECTION = 'SPECIFIC_SECTION'
    TARGET_STUDENT = 'SPECIFIC_STUDENT'
    TARGET_EMPLOYEE = 'SPECIFIC_EMPLOYEE'

    TARGET_CHOICES = (
        (TARGET_ALL, 'Entire School'),
        (TARGET_PARENTS, 'All Parents'),
        (TARGET_STUDENTS, 'All Students'),
        (TARGET_TEACHERS, 'All Teachers'),
        (TARGET_STAFF, 'All Staff Members'),
        (TARGET_CLASS, 'Specific Class / Grade'),
        (TARGET_SECTION, 'Specific Section'),
        (TARGET_STUDENT, 'Specific Student'),
        (TARGET_EMPLOYEE, 'Specific Employee'),
    )

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='targets'
    )
    target_type = models.CharField(max_length=30, choices=TARGET_CHOICES, default=TARGET_ALL)
    grade_level = models.ForeignKey(
        'academics.GradeLevel',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='announcement_targets'
    )
    section = models.ForeignKey(
        'academics.Section',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='announcement_targets'
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='announcement_targets'
    )
    employee = models.ForeignKey(
        'hr.Employee',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='announcement_targets'
    )

    def __str__(self):
        detail = ""
        if self.target_type == self.TARGET_CLASS and self.grade_level:
            detail = f": {self.grade_level.name}"
        elif self.target_type == self.TARGET_SECTION and self.section:
            detail = f": {self.section}"
        elif self.target_type == self.TARGET_STUDENT and self.student:
            detail = f": {self.student.get_full_name()}"
        elif self.target_type == self.TARGET_EMPLOYEE and self.employee:
            detail = f": {self.employee.get_full_name()}"
        return f"{self.get_target_type_display()}{detail}"


class Notification(ExportModelOperationsMixin('notification'), TimeStampedModel):
    """
    Represents an individual notification sent across in-app, email, SMS, or WhatsApp channels.
    """
    CHANNEL_IN_APP = 'IN_APP'
    CHANNEL_EMAIL = 'EMAIL'
    CHANNEL_SMS = 'SMS'
    CHANNEL_WHATSAPP = 'WHATSAPP'

    CHANNEL_CHOICES = (
        (CHANNEL_IN_APP, 'In-App Notification'),
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
    )

    STATUS_PENDING = 'PENDING'
    STATUS_QUEUED = 'QUEUED'
    STATUS_SENT = 'SENT'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_READ = 'READ'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_READ, 'Read'),
        (STATUS_FAILED, 'Failed'),
    )

    PRIORITY_LOW = 'LOW'
    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'

    PRIORITY_CHOICES = (
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent / Emergency'),
    )

    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default='GENERAL')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    read_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ['-created_at' if hasattr(TimeStampedModel, 'created_at') else '-created']
        indexes = [
            models.Index(fields=['recipient_user', 'status']),
            models.Index(fields=['school', 'channel', 'status']),
        ]

    def __str__(self):
        return f"[{self.channel}] {self.title} -> {self.recipient_user.username} ({self.status})"

    @property
    def is_read(self) -> bool:
        return self.status == self.STATUS_READ


class NotificationPreference(ExportModelOperationsMixin('notification_preference'), TimeStampedModel):
    """
    User notification preferences per tenant school.
    Allows granular opting into/out of various communication alerts.
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    announcement_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=True)
    attendance_alerts = models.BooleanField(default=True)
    fee_alerts = models.BooleanField(default=True)
    exam_alerts = models.BooleanField(default=True)
    transport_alerts = models.BooleanField(default=True)
    library_alerts = models.BooleanField(default=True)
    hr_alerts = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'user'], name='unique_school_user_notification_pref')
        ]

    def __str__(self):
        return f"Prefs: {self.user.username} @ {self.school.name}"


class NotificationTemplate(ExportModelOperationsMixin('notification_template'), TimeStampedModel):
    """
    Configurable message templates for automated notifications.
    Uses safe regex placeholder variable expansion (e.g. {{student_name}}).
    """
    school = models.ForeignKey(
        'tenants.School',
        on_delete=models.CASCADE,
        related_name='notification_templates'
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=100)
    channel = models.CharField(
        max_length=20,
        choices=Notification.CHANNEL_CHOICES,
        default=Notification.CHANNEL_IN_APP
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    active = models.BooleanField(default=True)
    variables = models.JSONField(default=list, blank=True, help_text="Allowed variable placeholder keys")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ['code', 'channel']
        constraints = [
            models.UniqueConstraint(fields=['school', 'code', 'channel'], name='unique_school_template_code_channel')
        ]

    def __str__(self):
        return f"[{self.channel}] {self.name} ({self.code})"


class NotificationDeliveryLog(ExportModelOperationsMixin('notification_delivery_log'), models.Model):
    """
    Immutable audit trail for notification dispatch attempts.
    """
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )
    channel = models.CharField(max_length=20)
    provider = models.CharField(max_length=100, default='MockProvider')
    provider_message_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=Notification.STATUS_CHOICES)
    attempted_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"Log #{self.pk}: {self.channel} via {self.provider} [{self.status}]"
