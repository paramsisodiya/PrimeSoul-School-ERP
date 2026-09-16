from typing import Optional, List, Dict, Any
from django.db.models import Count, Q
from django.utils import timezone
from django_school_management.tenants.models import School
from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, Notification, NotificationDeliveryLog
)


def get_user_notifications(
    user,
    school: Optional[School] = None,
    unread_only: bool = False,
    notification_type: Optional[str] = None,
    channel: Optional[str] = None,
    limit: Optional[int] = None
):
    """
    Returns filtered in-app notifications for the specific user.
    """
    if not user or not user.is_authenticated:
        return Notification.objects.none()

    qs = Notification.objects.filter(recipient_user=user).select_related('school', 'announcement')

    if school:
        qs = qs.filter(school=school)

    if unread_only:
        qs = qs.exclude(status=Notification.STATUS_READ)

    if notification_type:
        qs = qs.filter(notification_type=notification_type)

    if channel:
        qs = qs.filter(channel=channel)

    qs = qs.order_by('-created')
    if limit:
        qs = qs[:limit]

    return qs


def get_user_unread_count(user, school: Optional[School] = None) -> int:
    """
    Returns count of unread notifications for the user.
    """
    if not user or not user.is_authenticated:
        return 0

    qs = Notification.objects.filter(
        recipient_user=user,
        status__in=[Notification.STATUS_PENDING, Notification.STATUS_QUEUED, Notification.STATUS_SENT, Notification.STATUS_DELIVERED]
    )
    if school:
        qs = qs.filter(school=school)
    return qs.count()


def get_active_announcements_for_user(user, school: School) -> List[Announcement]:
    """
    Retrieves active published announcements targeted at the given user or their roles/classes.
    """
    now = timezone.now()
    base_qs = Announcement.objects.filter(
        school=school,
        status=Announcement.STATUS_PUBLISHED
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).prefetch_related('targets')

    if not user or not user.is_authenticated:
        # Only announcements targeted to ALL_SCHOOL
        return list(base_qs.filter(targets__target_type=AnnouncementTarget.TARGET_ALL).distinct())

    if user.is_superuser:
        return list(base_qs.distinct())

    # Build target matching filters (Untargeted or ALL_SCHOOL announcements are visible to everyone in the school)
    target_conditions = Q(targets__target_type=AnnouncementTarget.TARGET_ALL) | Q(targets__isnull=True)

    # Check Admin / Staff / Faculty roles
    is_staff_role = (
        user.is_staff or
        user.groups.filter(name__in=[
            'School Admin', 'Principal', 'Vice Principal', 'Academic Coordinator',
            'Teacher', 'Accountant', 'Receptionist', 'Librarian', 'Transport Manager'
        ]).exists()
    )
    if is_staff_role:
        target_conditions |= Q(targets__target_type__in=[AnnouncementTarget.TARGET_STAFF, AnnouncementTarget.TARGET_TEACHERS])

    # Check Parent
    if hasattr(user, 'parent_profile'):
        target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_PARENTS)
        # Parent child classrooms
        child_grades = user.parent_profile.student_relationships.values_list('student__grade_level_id', flat=True)
        child_sections = user.parent_profile.student_relationships.values_list('student__section_id', flat=True)
        child_students = user.parent_profile.student_relationships.values_list('student_id', flat=True)

        if child_grades:
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_CLASS, targets__grade_level_id__in=child_grades)
        if child_sections:
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_SECTION, targets__section_id__in=child_sections)
        if child_students:
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_STUDENT, targets__student_id__in=child_students)

    # Check Student
    if hasattr(user, 'student_profile'):
        student = user.student_profile
        target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_STUDENTS)
        target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_STUDENT, targets__student=student)
        if student.grade_level:
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_CLASS, targets__grade_level=student.grade_level)
        if student.section:
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_SECTION, targets__section=student.section)

    # Check Teacher / Staff employee record
    if hasattr(user, 'employee_profiles') and user.employee_profiles.exists():
        employee = user.employee_profiles.first()
        target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_STAFF)
        target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_EMPLOYEE, targets__employee=employee)
        if employee.designation and employee.designation.category == 'TEACHING':
            target_conditions |= Q(targets__target_type=AnnouncementTarget.TARGET_TEACHERS)

    return list(base_qs.filter(target_conditions).distinct().order_by('-published_at', '-created'))


def get_communication_dashboard_metrics(school: School) -> Dict[str, Any]:
    """
    Calculates aggregated communication performance and delivery metrics.
    """
    announcements_qs = Announcement.objects.filter(school=school)
    notifications_qs = Notification.objects.filter(school=school)

    announcement_stats = announcements_qs.aggregate(
        total=Count('id'),
        published=Count('id', filter=Q(status=Announcement.STATUS_PUBLISHED)),
        scheduled=Count('id', filter=Q(status=Announcement.STATUS_SCHEDULED)),
        draft=Count('id', filter=Q(status=Announcement.STATUS_DRAFT)),
        archived=Count('id', filter=Q(status=Announcement.STATUS_ARCHIVED)),
    )

    notification_stats = notifications_qs.aggregate(
        total_notifications=Count('id'),
        delivered=Count('id', filter=Q(status__in=[Notification.STATUS_DELIVERED, Notification.STATUS_READ])),
        read=Count('id', filter=Q(status=Notification.STATUS_READ)),
        failed=Count('id', filter=Q(status=Notification.STATUS_FAILED)),
        pending=Count('id', filter=Q(status__in=[Notification.STATUS_PENDING, Notification.STATUS_QUEUED])),
    )

    channel_breakdown = dict(
        notifications_qs.values('channel').annotate(count=Count('id')).values_list('channel', 'count')
    )

    return {
        "total_announcements": announcement_stats['total'] or 0,
        "published_announcements": announcement_stats['published'] or 0,
        "scheduled_announcements": announcement_stats['scheduled'] or 0,
        "draft_announcements": announcement_stats['draft'] or 0,
        "total_notifications": notification_stats['total_notifications'] or 0,
        "delivered_notifications": notification_stats['delivered'] or 0,
        "read_notifications": notification_stats['read'] or 0,
        "failed_notifications": notification_stats['failed'] or 0,
        "pending_notifications": notification_stats['pending'] or 0,
        "channel_breakdown": channel_breakdown,
    }


def get_announcement_delivery_summary(announcement: Announcement) -> Dict[str, Any]:
    """
    Returns delivery statistics for a specific announcement.
    """
    notifs = announcement.notifications.all()
    stats = notifs.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status__in=[Notification.STATUS_DELIVERED, Notification.STATUS_READ])),
        read=Count('id', filter=Q(status=Notification.STATUS_READ)),
        failed=Count('id', filter=Q(status=Notification.STATUS_FAILED)),
    )
    return {
        "total_recipients": stats['total'] or 0,
        "delivered_count": stats['delivered'] or 0,
        "read_count": stats['read'] or 0,
        "failed_count": stats['failed'] or 0,
    }
