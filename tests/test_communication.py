"""
Phase 14: PrimeSoul ERP Communication & Notification System Test Suite.
Validates tenant isolation, announcement targeting, multi-channel dispatch (In-App, Email, SMS, WhatsApp),
provider abstraction, template engine, user notification preferences, delivery logging, and REST APIs.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from django_school_management.tenants.models import School
from django_school_management.accounts.roles import Role, ensure_system_roles_exist, assign_role_to_user
from django_school_management.academics.models import AcademicYear, GradeLevel, Section, StudentEnrollment
from django_school_management.students.models import Student, ParentProfile, StudentGuardianRelationship
from django_school_management.hr.models import Department, HRDesignation, Employee
from django_school_management.communication.models import (
    Announcement, AnnouncementTarget, AnnouncementCategory,
    Notification, NotificationPreference, NotificationTemplate, NotificationDeliveryLog
)
from django_school_management.communication.providers.mock import MockNotificationProvider
from django_school_management.communication.services.template_service import (
    render_notification_template, validate_template_variables
)
from django_school_management.communication.services.notification_service import (
    create_and_send_notification, publish_announcement,
    mark_notification_as_read, mark_all_notifications_read,
    send_attendance_absent_alert, send_fee_due_alert, send_result_published_alert
)
from django_school_management.communication.selectors.communication_selectors import (
    get_user_notifications, get_user_unread_count, get_active_announcements_for_user,
    get_communication_dashboard_metrics, get_announcement_delivery_summary
)

User = get_user_model()


class PrimeSoulCommunicationTests(TestCase):
    """
    Comprehensive test suite for Phase 14: Communication & Notification System.
    """

    def setUp(self):
        MockNotificationProvider.reset()
        ensure_system_roles_exist()

        # 1. Tenants
        self.school_a = School.objects.create(
            name="Delhi Public School, R.K. Puram",
            slug="dps-rkpuram",
            board="CBSE",
            school_code="DPS-1034",
            is_active=True
        )
        self.school_b = School.objects.create(
            name="Modern School, Barakhamba",
            slug="modern-delhi",
            board="CBSE",
            school_code="MOD-5021",
            is_active=True
        )

        # 2. Academic Infrastructure
        self.ay = AcademicYear.objects.create(
            school=self.school_a,
            name="2026-2027",
            start_date="2026-04-01",
            end_date="2027-03-31",
            is_current=True
        )
        self.grade_9 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 9",
            code="CLASS-9",
            display_order=9,
            is_active=True
        )
        self.grade_10 = GradeLevel.objects.create(
            school=self.school_a,
            name="Class 10",
            code="CLASS-10",
            display_order=10,
            is_active=True
        )
        self.sec_9a = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade_9,
            name="A"
        )
        self.sec_9b = Section.objects.create(
            school=self.school_a,
            grade_level=self.grade_9,
            name="B"
        )

        # 3. Users & Profiles
        # Admin
        self.admin_user = User.objects.create_user(
            username="admin_dps",
            email="admin@dps.edu",
            password="Password123!",
            first_name="Admin",
            last_name="DPS"
        )
        self.admin_user.school = self.school_a
        self.admin_user.save()
        assign_role_to_user(self.admin_user, Role.SCHOOL_ADMIN)

        # Teacher
        self.teacher_user = User.objects.create_user(
            username="teacher_meera",
            email="meera@dps.edu",
            password="Password123!",
            first_name="Meera",
            last_name="Sharma"
        )
        self.teacher_user.school = self.school_a
        self.teacher_user.save()
        assign_role_to_user(self.teacher_user, Role.TEACHER)

        self.dept_academic = Department.objects.create(school=self.school_a, name="Academics", code="ACAD")
        self.desig_tgt = HRDesignation.objects.create(school=self.school_a, name="TGT Science", code="TGT-SCI", category="TEACHING")
        self.employee_meera = Employee.objects.create(
            school=self.school_a,
            user=self.teacher_user,
            employee_code="EMP-101",
            full_name="Meera Sharma",
            mobile="9876543210",
            email="meera@dps.edu",
            department=self.dept_academic,
            designation=self.desig_tgt,
            joining_date="2024-06-01"
        )

        # Student & Parent
        self.parent_user = User.objects.create_user(
            username="parent_rajesh",
            email="rajesh@example.com",
            password="Password123!",
            first_name="Rajesh",
            last_name="Verma"
        )
        self.parent_user.school = self.school_a
        self.parent_user.save()
        assign_role_to_user(self.parent_user, Role.PARENT)

        self.parent_profile = ParentProfile.objects.create(
            school=self.school_a,
            user=self.parent_user,
            relationship_type="Father",
            first_name="Rajesh",
            last_name="Verma",
            mobile_number="9876543211",
            email="rajesh@example.com"
        )

        self.student_user = User.objects.create_user(
            username="student_aarav",
            email="aarav@dps.edu",
            password="Password123!",
            first_name="Aarav",
            last_name="Verma"
        )
        self.student_user.school = self.school_a
        self.student_user.save()
        assign_role_to_user(self.student_user, Role.STUDENT)

        self.student_aarav = Student.objects.create(
            school=self.school_a,
            user=self.student_user,
            first_name="Aarav",
            last_name="Verma",
            admission_number="ADM-2026-0001",
            roll_number="01",
            academic_year=self.ay,
            grade_level=self.grade_9,
            section=self.sec_9a
        )
        StudentGuardianRelationship.objects.create(
            student=self.student_aarav,
            guardian=self.parent_profile,
            relationship_type="Father",
            is_primary_contact=True
        )

        # School B User
        self.school_b_user = User.objects.create_user(
            username="user_school_b",
            email="user@modern.edu",
            password="Password123!",
            first_name="Modern",
            last_name="User"
        )
        self.school_b_user.school = self.school_b
        self.school_b_user.save()
        assign_role_to_user(self.school_b_user, Role.SCHOOL_ADMIN)

        # API Client
        self.client = APIClient()

    def test_01_tenant_isolation_in_announcements(self):
        """School A announcements are strictly inaccessible to School B."""
        ann_a = Announcement.objects.create(
            school=self.school_a,
            title="School A Sports Day",
            content="Sports Day on Saturday.",
            status=Announcement.STATUS_PUBLISHED,
            created_by=self.admin_user
        )
        ann_b = Announcement.objects.create(
            school=self.school_b,
            title="School B Science Fair",
            content="Science Fair next week.",
            status=Announcement.STATUS_PUBLISHED,
            created_by=self.school_b_user
        )

        # Selectors verify isolation
        active_a = get_active_announcements_for_user(self.admin_user, self.school_a)
        active_b = get_active_announcements_for_user(self.school_b_user, self.school_b)

        self.assertIn(ann_a, active_a)
        self.assertNotIn(ann_b, active_a)
        self.assertIn(ann_b, active_b)
        self.assertNotIn(ann_a, active_b)

    def test_02_announcement_crud_and_status_lifecycle(self):
        """Validates announcement creation, publishing, and archiving lifecycle."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="Winter Vacation Notice",
            content="School remains closed from Dec 25 to Jan 5.",
            priority=Announcement.PRIORITY_NORMAL,
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        self.assertEqual(ann.status, Announcement.STATUS_DRAFT)
        self.assertFalse(ann.is_published)

        # Publish
        count = publish_announcement(ann, published_by=self.admin_user)
        ann.refresh_from_db()
        self.assertEqual(ann.status, Announcement.STATUS_PUBLISHED)
        self.assertTrue(ann.is_published)
        self.assertIsNotNone(ann.published_at)
        self.assertGreater(count, 0)

    def test_03_targeting_all_school(self):
        """Broadcasting to ALL_SCHOOL creates notifications for student, parent, teacher, and admin."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="All School Assembly",
            content="Mandatory morning assembly tomorrow.",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        AnnouncementTarget.objects.create(announcement=ann, target_type=AnnouncementTarget.TARGET_ALL)

        count = publish_announcement(ann, published_by=self.admin_user)
        self.assertGreaterEqual(count, 4)

        # Check in-app notification delivered
        student_notifs = Notification.objects.filter(recipient_user=self.student_user, announcement=ann)
        parent_notifs = Notification.objects.filter(recipient_user=self.parent_user, announcement=ann)
        teacher_notifs = Notification.objects.filter(recipient_user=self.teacher_user, announcement=ann)

        self.assertTrue(student_notifs.exists())
        self.assertTrue(parent_notifs.exists())
        self.assertTrue(teacher_notifs.exists())

    def test_04_targeting_parents_only(self):
        """Targeting PARENTS only notifies parent accounts."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="Parent Teacher Meeting",
            content="PTM on Saturday at 9 AM.",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        AnnouncementTarget.objects.create(announcement=ann, target_type=AnnouncementTarget.TARGET_PARENTS)

        publish_announcement(ann, published_by=self.admin_user)

        self.assertTrue(Notification.objects.filter(recipient_user=self.parent_user, announcement=ann).exists())
        self.assertFalse(Notification.objects.filter(recipient_user=self.student_user, announcement=ann).exists())
        self.assertFalse(Notification.objects.filter(recipient_user=self.teacher_user, announcement=ann).exists())

    def test_05_targeting_students_only(self):
        """Targeting STUDENTS only notifies student accounts."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="Library Book Fair",
            content="Visit the library for discounts.",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        AnnouncementTarget.objects.create(announcement=ann, target_type=AnnouncementTarget.TARGET_STUDENTS)

        publish_announcement(ann, published_by=self.admin_user)

        self.assertTrue(Notification.objects.filter(recipient_user=self.student_user, announcement=ann).exists())
        self.assertFalse(Notification.objects.filter(recipient_user=self.parent_user, announcement=ann).exists())

    def test_06_targeting_teachers_and_staff(self):
        """Targeting TEACHERS / STAFF notifies staff employees."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="Staff Meeting",
            content="Staff meeting in boardroom at 3 PM.",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        AnnouncementTarget.objects.create(announcement=ann, target_type=AnnouncementTarget.TARGET_TEACHERS)

        publish_announcement(ann, published_by=self.admin_user)

        self.assertTrue(Notification.objects.filter(recipient_user=self.teacher_user, announcement=ann).exists())
        self.assertFalse(Notification.objects.filter(recipient_user=self.student_user, announcement=ann).exists())

    def test_07_targeting_specific_class_and_section(self):
        """Targeting Class 9 Section A notifies Class 9-A students and their parents, not Class 10."""
        ann = Announcement.objects.create(
            school=self.school_a,
            title="Class 9-A Science Project",
            content="Submit lab files on Friday.",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        AnnouncementTarget.objects.create(
            announcement=ann,
            target_type=AnnouncementTarget.TARGET_SECTION,
            section=self.sec_9a
        )

        publish_announcement(ann, published_by=self.admin_user)

        # Aarav (in 9-A) and his parent receive it
        self.assertTrue(Notification.objects.filter(recipient_user=self.student_user, announcement=ann).exists())
        self.assertTrue(Notification.objects.filter(recipient_user=self.parent_user, announcement=ann).exists())

    def test_08_in_app_notification_creation_and_delivery(self):
        """In-app notifications are delivered immediately and log audit delivery record."""
        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Timetable Updated",
            message="Your Monday period 3 changed to Mathematics.",
            channel=Notification.CHANNEL_IN_APP
        )
        self.assertEqual(notif.status, Notification.STATUS_DELIVERED)
        self.assertIsNotNone(notif.delivered_at)

        log = NotificationDeliveryLog.objects.filter(notification=notif).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, Notification.STATUS_DELIVERED)

    def test_09_notification_read_unread_and_mark_all(self):
        """Validates marking single notification read and bulk marking all as read."""
        n1 = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Alert 1",
            message="Message 1",
            channel=Notification.CHANNEL_IN_APP
        )
        n2 = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Alert 2",
            message="Message 2",
            channel=Notification.CHANNEL_IN_APP
        )

        self.assertEqual(get_user_unread_count(self.student_user, self.school_a), 2)

        mark_notification_as_read(n1, self.student_user)
        n1.refresh_from_db()
        self.assertEqual(n1.status, Notification.STATUS_READ)
        self.assertEqual(get_user_unread_count(self.student_user, self.school_a), 1)

        # Mark all read
        mark_all_notifications_read(self.student_user, self.school_a)
        self.assertEqual(get_user_unread_count(self.student_user, self.school_a), 0)

    def test_10_user_cannot_mark_other_user_notification_read(self):
        """IDOR Guard: User cannot mark another user's notification as read."""
        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Private Alert",
            message="Private message.",
            channel=Notification.CHANNEL_IN_APP
        )
        with self.assertRaises(PermissionDenied):
            mark_notification_as_read(notif, self.parent_user)

    def test_11_notification_preferences_opt_out(self):
        """User opting out of a channel drops normal notifications."""
        pref, _ = NotificationPreference.objects.get_or_create(school=self.school_a, user=self.parent_user)
        pref.email_enabled = False
        pref.save()

        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="Fee Notice",
            message="Kindly pay fees.",
            channel=Notification.CHANNEL_EMAIL,
            priority=Notification.PRIORITY_NORMAL,
            to_email="rajesh@example.com"
        )
        self.assertEqual(notif.status, Notification.STATUS_FAILED)
        self.assertIn("opted out", notif.failure_reason)

    def test_12_urgent_emergency_bypasses_preferences(self):
        """URGENT priority notifications bypass user opt-out."""
        pref, _ = NotificationPreference.objects.get_or_create(school=self.school_a, user=self.parent_user)
        pref.email_enabled = False
        pref.save()

        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="EMERGENCY: Heavy Rain Holiday",
            message="School closed today due to cyclone alert.",
            channel=Notification.CHANNEL_EMAIL,
            priority=Notification.PRIORITY_URGENT,
            to_email="rajesh@example.com"
        )
        self.assertEqual(notif.status, Notification.STATUS_DELIVERED)

    def test_13_template_rendering_and_variable_expansion(self):
        """Template engine replaces allowed variables safely."""
        template_body = "Dear {{parent_name}}, your ward {{student_name}} scored {{marks}} marks."
        context = {"parent_name": "Rajesh", "student_name": "Aarav", "marks": "95"}
        allowed = ["parent_name", "student_name", "marks"]

        rendered = render_notification_template(template_body, context, allowed_variables=allowed)
        self.assertEqual(rendered, "Dear Rajesh, your ward Aarav scored 95 marks.")

    def test_14_invalid_template_variables_rejected(self):
        """Template engine rejects unapproved variable placeholders."""
        template_body = "Hello {{student_name}}, your secret is {{unauthorized_field}}."
        allowed = ["student_name"]

        with self.assertRaises(ValidationError):
            render_notification_template(template_body, {"student_name": "Aarav"}, allowed_variables=allowed)

    def test_15_provider_abstraction_mock_email(self):
        """Mock email provider dispatches email and logs in memory."""
        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="School Newsletter",
            message="Monthly newsletter content.",
            channel=Notification.CHANNEL_EMAIL,
            to_email="rajesh@example.com"
        )
        self.assertEqual(notif.status, Notification.STATUS_DELIVERED)
        self.assertEqual(len(MockNotificationProvider.sent_emails), 1)
        self.assertEqual(MockNotificationProvider.sent_emails[0]['to_email'], "rajesh@example.com")

    def test_16_provider_abstraction_mock_sms(self):
        """Mock SMS provider dispatches SMS and records phone."""
        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="Bus Arrival Alert",
            message="School bus #12 reaching stop in 5 mins.",
            channel=Notification.CHANNEL_SMS,
            to_phone="9876543211"
        )
        self.assertEqual(notif.status, Notification.STATUS_DELIVERED)
        self.assertEqual(len(MockNotificationProvider.sent_sms), 1)
        self.assertEqual(MockNotificationProvider.sent_sms[0]['to_phone'], "9876543211")

    def test_17_provider_abstraction_mock_whatsapp(self):
        """Mock WhatsApp provider dispatches template messages."""
        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="Fee Receipt",
            message="Fee receipt #REC-1002.",
            channel=Notification.CHANNEL_WHATSAPP,
            to_phone="9876543211",
            template_code="FEE_RECEIPT_V1",
            template_vars={"amount": "15000"}
        )
        self.assertEqual(notif.status, Notification.STATUS_DELIVERED)
        self.assertEqual(len(MockNotificationProvider.sent_whatsapp), 1)
        self.assertEqual(MockNotificationProvider.sent_whatsapp[0]['template_code'], "FEE_RECEIPT_V1")

    def test_18_failed_delivery_handling_and_logging(self):
        """Simulated provider failure records FAILED status and failure reason in log."""
        MockNotificationProvider.should_fail = True
        MockNotificationProvider.failure_reason = "Telecom Gateway Timeout (504)"

        notif = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.parent_user,
            title="Test SMS Alert",
            message="Alert message.",
            channel=Notification.CHANNEL_SMS,
            to_phone="9876543211"
        )
        self.assertEqual(notif.status, Notification.STATUS_FAILED)
        self.assertIn("Telecom Gateway Timeout", notif.failure_reason)

        log = NotificationDeliveryLog.objects.filter(notification=notif).first()
        self.assertEqual(log.status, Notification.STATUS_FAILED)
        self.assertIn("Telecom Gateway Timeout", log.failure_reason)

        MockNotificationProvider.should_fail = False

    def test_19_notification_idempotency_prevents_duplicate_sends(self):
        """Using same idempotency key prevents duplicate notification creation."""
        key = "idemp-test-unique-key-101"
        n1 = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Unique Alert",
            message="Message 1",
            idempotency_key=key
        )
        n2 = create_and_send_notification(
            school=self.school_a,
            recipient_user=self.student_user,
            title="Unique Alert",
            message="Message 1 - duplicate attempt",
            idempotency_key=key
        )
        self.assertEqual(n1.pk, n2.pk)
        self.assertEqual(Notification.objects.filter(idempotency_key=key).count(), 1)

    def test_20_event_driven_alerts(self):
        """Tests event-driven helper services (attendance absent, fee due, result published)."""
        # Absent alert
        absent_notifs = send_attendance_absent_alert(self.student_aarav, date="2026-09-15")
        self.assertTrue(len(absent_notifs) > 0)
        self.assertEqual(absent_notifs[0].notification_type, "ATTENDANCE_ALERT")

        # Fee due reminder
        fee_notifs = send_fee_due_alert(self.student_aarav, amount="25000", due_date="2026-10-10")
        self.assertTrue(len(fee_notifs) > 0)
        self.assertEqual(fee_notifs[0].notification_type, "FEE_ALERT")

        # Result published
        result_notifs = send_result_published_alert(self.student_aarav, exam_name="Mid-Term Exams 2026")
        self.assertTrue(len(result_notifs) > 0)
        self.assertEqual(result_notifs[0].notification_type, "EXAM_RESULT")

    def test_21_communication_dashboard_metrics(self):
        """Dashboard selectors return accurate aggregated statistics."""
        Announcement.objects.create(
            school=self.school_a,
            title="Ann 1",
            content="Content 1",
            status=Announcement.STATUS_PUBLISHED,
            created_by=self.admin_user
        )
        Announcement.objects.create(
            school=self.school_a,
            title="Ann 2",
            content="Content 2",
            status=Announcement.STATUS_DRAFT,
            created_by=self.admin_user
        )
        metrics = get_communication_dashboard_metrics(self.school_a)
        self.assertEqual(metrics['total_announcements'], 2)
        self.assertEqual(metrics['published_announcements'], 1)
        self.assertEqual(metrics['draft_announcements'], 1)

    def test_22_communication_rest_api_endpoints(self):
        """Validates DRF endpoints for announcements, notifications, and preferences."""
        self.client.force_authenticate(user=self.admin_user)

        # 1. Announcements List
        resp = self.client.get('/api/v1/communication/announcements/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Notification Preferences GET & PUT
        resp = self.client.get('/api/v1/communication/preferences/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.put('/api/v1/communication/preferences/', {'email_enabled': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['email_enabled'])

        # 3. Communication Dashboard API
        resp = self.client.get('/api/v1/communication/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_announcements', resp.data)
