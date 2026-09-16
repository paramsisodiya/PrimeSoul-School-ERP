import logging
from typing import Optional, List, Dict, Any, Set
from django.db import transaction, models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from django_school_management.tenants.models import School
from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, Notification,
    NotificationPreference, NotificationTemplate, NotificationDeliveryLog
)
from django_school_management.communication.providers.factory import get_notification_provider
from django_school_management.communication.services.template_service import render_notification_template

User = get_user_model()
logger = logging.getLogger(__name__)


def is_channel_enabled_for_user(user, school: School, channel: str, alert_type: str = 'general') -> bool:
    """
    Checks if a user's notification preferences allow delivery for this channel and alert type.
    """
    pref = NotificationPreference.objects.filter(school=school, user=user).first()
    if not pref:
        return True  # Default to enabled if no custom preference record exists

    # Channel toggle
    if channel == Notification.CHANNEL_EMAIL and not pref.email_enabled:
        return False
    if channel == Notification.CHANNEL_SMS and not pref.sms_enabled:
        return False
    if channel == Notification.CHANNEL_WHATSAPP and not pref.whatsapp_enabled:
        return False

    # Alert type toggle
    if alert_type == 'attendance' and not pref.attendance_alerts:
        return False
    if alert_type == 'fee' and not pref.fee_alerts:
        return False
    if alert_type == 'exam' and not pref.exam_alerts:
        return False
    if alert_type == 'transport' and not pref.transport_alerts:
        return False
    if alert_type == 'library' and not pref.library_alerts:
        return False
    if alert_type == 'hr' and not pref.hr_alerts:
        return False
    if alert_type == 'announcement' and not pref.announcement_enabled:
        return False

    return True


@transaction.atomic
def create_and_send_notification(
    school: School,
    recipient_user,
    title: str,
    message: str,
    notification_type: str = 'GENERAL',
    priority: str = Notification.PRIORITY_NORMAL,
    channel: str = Notification.CHANNEL_IN_APP,
    announcement: Optional[Announcement] = None,
    idempotency_key: Optional[str] = None,
    force: bool = False,
    alert_type: str = 'general',
    to_phone: Optional[str] = None,
    to_email: Optional[str] = None,
    template_code: Optional[str] = None,
    template_vars: Optional[Dict[str, Any]] = None
) -> Notification:
    """
    Creates and dispatches a single notification to a recipient user.
    Enforces idempotency, user preferences, delivery logging, and status tracking.
    """
    # 1. Idempotency Check: Avoid duplicate deliveries
    if idempotency_key:
        existing = Notification.objects.filter(
            school=school,
            recipient_user=recipient_user,
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing

    # 2. Preference Check: Critical/Urgent priority bypasses preferences
    is_urgent = (priority == Notification.PRIORITY_URGENT)
    if not is_urgent and not force:
        if not is_channel_enabled_for_user(recipient_user, school, channel, alert_type):
            logger.info(f"Notification {title} dropped: User {recipient_user} opted out of {channel}/{alert_type}")
            # Still record notification as FAILED or skip creation
            notification = Notification.objects.create(
                school=school,
                recipient_user=recipient_user,
                announcement=announcement,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                channel=channel,
                status=Notification.STATUS_FAILED,
                failure_reason="User opted out via notification preferences",
                idempotency_key=idempotency_key
            )
            return notification

    # 3. Create Notification Record
    notification = Notification.objects.create(
        school=school,
        recipient_user=recipient_user,
        announcement=announcement,
        title=title,
        message=message,
        notification_type=notification_type,
        priority=priority,
        channel=channel,
        status=Notification.STATUS_PENDING,
        idempotency_key=idempotency_key
    )

    # 4. Dispatch via Provider
    provider = get_notification_provider(channel)
    provider_name = getattr(provider, 'name', 'GenericProvider')
    now = timezone.now()

    if channel == Notification.CHANNEL_IN_APP:
        # In-App is delivered immediately on creation
        notification.status = Notification.STATUS_DELIVERED
        notification.delivered_at = now
        notification.save(update_fields=['status', 'delivered_at'])

        NotificationDeliveryLog.objects.create(
            notification=notification,
            channel=channel,
            provider="InAppBus",
            provider_message_id=f"inapp-{notification.pk}",
            status=Notification.STATUS_DELIVERED,
            delivered_at=now
        )
        return notification

    elif channel == Notification.CHANNEL_EMAIL:
        email_addr = to_email or recipient_user.email
        if not email_addr:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = "No email address found for recipient"
            notification.save(update_fields=['status', 'failed_at', 'failure_reason'])
            return notification

        res = provider.send_email(to_email=email_addr, subject=title, body_html=message)
        if res.success:
            notification.status = res.status
            notification.delivered_at = now if res.status == Notification.STATUS_DELIVERED else None
        else:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = res.error_message

        notification.save(update_fields=['status', 'delivered_at', 'failed_at', 'failure_reason'])
        NotificationDeliveryLog.objects.create(
            notification=notification,
            channel=channel,
            provider=provider_name,
            provider_message_id=res.provider_message_id,
            status=notification.status,
            delivered_at=notification.delivered_at,
            failed_at=notification.failed_at,
            failure_reason=notification.failure_reason
        )
        return notification

    elif channel == Notification.CHANNEL_SMS:
        phone_num = to_phone
        if not phone_num:
            # Check profile for phone
            if hasattr(recipient_user, 'parent_profile'):
                phone_num = recipient_user.parent_profile.mobile_number
            elif hasattr(recipient_user, 'student_profile'):
                phone_num = recipient_user.student_profile.guardian_mobile_number
            elif hasattr(recipient_user, 'employee_profile'):
                phone_num = recipient_user.employee_profile.phone_number

        if not phone_num:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = "No phone number found for recipient"
            notification.save(update_fields=['status', 'failed_at', 'failure_reason'])
            return notification

        res = provider.send_sms(to_phone=phone_num, message=message)
        if res.success:
            notification.status = res.status
            notification.delivered_at = now if res.status == Notification.STATUS_DELIVERED else None
        else:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = res.error_message

        notification.save(update_fields=['status', 'delivered_at', 'failed_at', 'failure_reason'])
        NotificationDeliveryLog.objects.create(
            notification=notification,
            channel=channel,
            provider=provider_name,
            provider_message_id=res.provider_message_id,
            status=notification.status,
            delivered_at=notification.delivered_at,
            failed_at=notification.failed_at,
            failure_reason=notification.failure_reason
        )
        return notification

    elif channel == Notification.CHANNEL_WHATSAPP:
        phone_num = to_phone
        if not phone_num and hasattr(recipient_user, 'parent_profile'):
            phone_num = recipient_user.parent_profile.mobile_number

        if not phone_num:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = "No phone number found for WhatsApp recipient"
            notification.save(update_fields=['status', 'failed_at', 'failure_reason'])
            return notification

        res = provider.send_whatsapp(
            to_phone=phone_num,
            template_code=template_code or 'GENERAL_ALERT',
            variables=template_vars or {},
            body=message
        )
        if res.success:
            notification.status = res.status
            notification.delivered_at = now if res.status == Notification.STATUS_DELIVERED else None
        else:
            notification.status = Notification.STATUS_FAILED
            notification.failed_at = now
            notification.failure_reason = res.error_message

        notification.save(update_fields=['status', 'delivered_at', 'failed_at', 'failure_reason'])
        NotificationDeliveryLog.objects.create(
            notification=notification,
            channel=channel,
            provider=provider_name,
            provider_message_id=res.provider_message_id,
            status=notification.status,
            delivered_at=notification.delivered_at,
            failed_at=notification.failed_at,
            failure_reason=notification.failure_reason
        )
        return notification

    return notification


@transaction.atomic
def publish_announcement(announcement: Announcement, published_by=None) -> int:
    """
    Publishes an announcement and creates notifications for all resolved recipient users.
    Returns total count of notifications generated.
    """
    announcement.status = Announcement.STATUS_PUBLISHED
    announcement.published_at = timezone.now()
    if published_by and not announcement.created_by:
        announcement.created_by = published_by
    announcement.save(update_fields=['status', 'published_at', 'created_by'] if published_by else ['status', 'published_at'])

    # Resolve target audience
    school = announcement.school
    recipient_users: Set[User] = set()
    targets = announcement.targets.all()

    if not targets.exists():
        # Default to ALL_SCHOOL if no target records exist
        all_users = User.objects.filter(
            Q(school=school) | Q(student_profile__school=school) | Q(parent_profile__school=school) | Q(employee_profiles__school=school) | Q(teacher_profile__school=school)
        ).distinct()
        recipient_users.update(all_users)
    else:
        for t in targets:
            if t.target_type == AnnouncementTarget.TARGET_ALL:
                users = User.objects.filter(
                    Q(school=school) | Q(student_profile__school=school) | Q(parent_profile__school=school) | Q(employee_profiles__school=school) | Q(teacher_profile__school=school)
                ).distinct()
                recipient_users.update(users)

            elif t.target_type == AnnouncementTarget.TARGET_PARENTS:
                parent_users = User.objects.filter(parent_profile__school=school).distinct()
                recipient_users.update(parent_users)

            elif t.target_type == AnnouncementTarget.TARGET_STUDENTS:
                student_users = User.objects.filter(student_profile__school=school).distinct()
                recipient_users.update(student_users)

            elif t.target_type in (AnnouncementTarget.TARGET_TEACHERS, AnnouncementTarget.TARGET_STAFF):
                staff_users = User.objects.filter(
                    Q(employee_profiles__school=school) | Q(teacher_profile__school=school) | Q(school=school, groups__name__in=['Teacher', 'Principal', 'School Admin', 'Vice Principal', 'Academic Coordinator', 'Accountant', 'Receptionist', 'Librarian', 'Transport Manager'])
                ).distinct()
                recipient_users.update(staff_users)

            elif t.target_type == AnnouncementTarget.TARGET_CLASS and t.grade_level:
                from django_school_management.students.models import Student, StudentGuardianRelationship
                # Students enrolled in grade_level
                student_users = User.objects.filter(student_profile__grade_level=t.grade_level).distinct()
                recipient_users.update(student_users)
                # Parents of students in grade_level
                parent_users = User.objects.filter(
                    parent_profile__student_relationships__student__grade_level=t.grade_level
                ).distinct()
                recipient_users.update(parent_users)

            elif t.target_type == AnnouncementTarget.TARGET_SECTION and t.section:
                from django_school_management.students.models import Student
                student_users = User.objects.filter(student_profile__section=t.section).distinct()
                recipient_users.update(student_users)
                parent_users = User.objects.filter(
                    parent_profile__student_relationships__student__section=t.section
                ).distinct()
                recipient_users.update(parent_users)

            elif t.target_type == AnnouncementTarget.TARGET_STUDENT and t.student:
                if t.student.user:
                    recipient_users.add(t.student.user)
                # Add parents of this student
                for rel in t.student.guardian_relationships.select_related('guardian__user').all():
                    if rel.guardian.user:
                        recipient_users.add(rel.guardian.user)

            elif t.target_type == AnnouncementTarget.TARGET_EMPLOYEE and t.employee:
                if t.employee.user:
                    recipient_users.add(t.employee.user)

    count = 0
    for u in recipient_users:
        create_and_send_notification(
            school=school,
            recipient_user=u,
            title=announcement.title,
            message=announcement.content,
            notification_type='ANNOUNCEMENT',
            priority=announcement.priority,
            channel=Notification.CHANNEL_IN_APP,
            announcement=announcement,
            idempotency_key=f"announcement-{announcement.pk}-user-{u.pk}",
            alert_type='announcement'
        )
        count += 1

    return count


def mark_notification_as_read(notification: Notification, user) -> Notification:
    """
    Marks an in-app notification as READ by the authorized owner.
    """
    if notification.recipient_user != user and not user.is_superuser:
        raise PermissionDenied("Cannot mark other users' notifications as read")

    if notification.status != Notification.STATUS_READ:
        notification.status = Notification.STATUS_READ
        notification.read_at = timezone.now()
        notification.save(update_fields=['status', 'read_at'])
    return notification


def mark_all_notifications_read(user, school: Optional[School] = None) -> int:
    """
    Marks all unread in-app notifications for the given user as read.
    """
    qs = Notification.objects.filter(
        recipient_user=user,
        status__in=[Notification.STATUS_PENDING, Notification.STATUS_QUEUED, Notification.STATUS_SENT, Notification.STATUS_DELIVERED]
    )
    if school:
        qs = qs.filter(school=school)
    count = qs.update(status=Notification.STATUS_READ, read_at=timezone.now())
    return count


# ---------------------------------------------------------
# Event-driven Notification Hooks
# ---------------------------------------------------------

def send_attendance_absent_alert(student, date, school: Optional[School] = None) -> List[Notification]:
    """
    Dispatches attendance absence notification to student guardians.
    """
    school = school or student.school
    created_notifications = []
    guardians = student.guardian_relationships.select_related('guardian__user').all()

    for rel in guardians:
        guardian = rel.guardian
        if not guardian.user:
            continue

        title = f"Attendance Alert: {student.get_full_name()} was marked Absent"
        msg = f"Dear {guardian.get_full_name()}, your ward {student.get_full_name()} was marked Absent on {date}."

        notif = create_and_send_notification(
            school=school,
            recipient_user=guardian.user,
            title=title,
            message=msg,
            notification_type='ATTENDANCE_ALERT',
            priority=Notification.PRIORITY_HIGH,
            channel=Notification.CHANNEL_IN_APP,
            idempotency_key=f"absent-{student.pk}-{date}-{guardian.user.pk}",
            alert_type='attendance'
        )
        created_notifications.append(notif)

    return created_notifications


def send_fee_due_alert(student, amount, due_date, school: Optional[School] = None) -> List[Notification]:
    """
    Dispatches fee payment due reminder to parents.
    """
    school = school or student.school
    created_notifications = []
    guardians = student.guardian_relationships.select_related('guardian__user').all()

    for rel in guardians:
        guardian = rel.guardian
        if not guardian.user:
            continue

        title = f"Fee Due Reminder: ₹{amount} due on {due_date}"
        msg = f"Dear {guardian.get_full_name()}, fee amount ₹{amount} for {student.get_full_name()} is due on {due_date}. Kindly pay on time."

        notif = create_and_send_notification(
            school=school,
            recipient_user=guardian.user,
            title=title,
            message=msg,
            notification_type='FEE_ALERT',
            priority=Notification.PRIORITY_NORMAL,
            channel=Notification.CHANNEL_IN_APP,
            idempotency_key=f"fee-due-{student.pk}-{due_date}-{amount}-{guardian.user.pk}",
            alert_type='fee'
        )
        created_notifications.append(notif)

    return created_notifications


def send_result_published_alert(student, exam_name, school: Optional[School] = None) -> List[Notification]:
    """
    Dispatches result publication alert to student and parents.
    """
    school = school or student.school
    created_notifications = []
    recipients = []

    if student.user:
        recipients.append(student.user)

    for rel in student.guardian_relationships.select_related('guardian__user').all():
        if rel.guardian.user:
            recipients.append(rel.guardian.user)

    for u in recipients:
        title = f"Exam Result Published: {exam_name}"
        msg = f"The results for {exam_name} for student {student.get_full_name()} are now published and available on the portal."

        notif = create_and_send_notification(
            school=school,
            recipient_user=u,
            title=title,
            message=msg,
            notification_type='EXAM_RESULT',
            priority=Notification.PRIORITY_NORMAL,
            channel=Notification.CHANNEL_IN_APP,
            idempotency_key=f"result-{student.pk}-{exam_name}-{u.pk}",
            alert_type='exam'
        )
        created_notifications.append(notif)

    return created_notifications


def send_transport_update_alert(student, route_name: str, message: str, school: Optional[School] = None) -> List[Notification]:
    """
    Dispatches transport route/timing alert to parents.
    """
    school = school or student.school
    created_notifications = []
    guardians = student.guardian_relationships.select_related('guardian__user').all()

    for rel in guardians:
        guardian = rel.guardian
        if not guardian.user:
            continue

        title = f"Transport Update: Route {route_name}"
        notif = create_and_send_notification(
            school=school,
            recipient_user=guardian.user,
            title=title,
            message=message,
            notification_type='TRANSPORT_ALERT',
            priority=Notification.PRIORITY_HIGH,
            channel=Notification.CHANNEL_IN_APP,
            alert_type='transport'
        )
        created_notifications.append(notif)

    return created_notifications


def send_library_overdue_alert(member, book_title: str, due_date, fine_amount, school: Optional[School] = None) -> Optional[Notification]:
    """
    Dispatches library overdue alert to member user.
    """
    user = None
    if getattr(member, 'student', None) and member.student.user:
        user = member.student.user
    elif getattr(member, 'teacher', None) and member.teacher.user:
        user = member.teacher.user

    if not user:
        return None

    school = school or getattr(member, 'school', None)
    title = f"Library Overdue Notice: {book_title}"
    msg = f"The borrowed book '{book_title}' was due on {due_date}. Accumulated fine: ₹{fine_amount}. Please return promptly."

    return create_and_send_notification(
        school=school,
        recipient_user=user,
        title=title,
        message=msg,
        notification_type='LIBRARY_ALERT',
        priority=Notification.PRIORITY_NORMAL,
        channel=Notification.CHANNEL_IN_APP,
        alert_type='library'
    )


def send_leave_status_alert(employee, leave_request, school: Optional[School] = None) -> Optional[Notification]:
    """
    Dispatches leave approval/rejection notification to staff member.
    """
    if not employee.user:
        return None

    school = school or employee.school
    title = f"Leave Request {leave_request.get_status_display()}: {leave_request.leave_type.name}"
    msg = f"Your leave application from {leave_request.start_date} to {leave_request.end_date} has been {leave_request.get_status_display().upper()}."

    return create_and_send_notification(
        school=school,
        recipient_user=employee.user,
        title=title,
        message=msg,
        notification_type='HR_ALERT',
        priority=Notification.PRIORITY_NORMAL,
        channel=Notification.CHANNEL_IN_APP,
        alert_type='hr'
    )
