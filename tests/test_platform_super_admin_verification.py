"""
Tests for Platform Super Admin verification, profile approval bypass, and onboarding behavior.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_school_management.accounts.services.common import profile_not_approved
from django_school_management.accounts.constants import ProfileApprovalStatusEnum

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['*'],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class PlatformSuperAdminVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Platform Superuser
        self.superuser = User.objects.create_superuser(
            username="platform_admin",
            email="platform_admin@primesoul.edu.in",
            password="StrongPassword123!"
        )

        # 2. Normal Unapproved User
        self.unapproved_user = User.objects.create_user(
            username="teacher_john",
            email="john@school.edu.in",
            password="Password123!",
            approval_status=ProfileApprovalStatusEnum.not_requested.value,
            requested_role="TEACHER"
        )

        # 3. Normal Approved User
        self.approved_user = User.objects.create_user(
            username="teacher_mary",
            email="mary@school.edu.in",
            password="Password123!",
            approval_status=ProfileApprovalStatusEnum.approved.value,
            requested_role="TEACHER"
        )

    def test_01_superuser_is_always_considered_approved(self):
        """profile_not_approved(user) must return False for superuser regardless of approval_status."""
        self.assertFalse(profile_not_approved(self.superuser))

        # Even if approval_status is 'n' or 'p', superuser is still treated as approved
        self.superuser.approval_status = ProfileApprovalStatusEnum.pending.value
        self.assertFalse(profile_not_approved(self.superuser))

        self.superuser.approval_status = ProfileApprovalStatusEnum.not_requested.value
        self.assertFalse(profile_not_approved(self.superuser))

    def test_02_normal_users_retain_existing_approval_behavior(self):
        """profile_not_approved(user) correctly distinguishes normal approved vs unapproved users."""
        self.assertTrue(profile_not_approved(self.unapproved_user))
        self.assertFalse(profile_not_approved(self.approved_user))

    def test_03_profile_page_does_not_show_pending_or_unverified_for_superuser(self):
        """GET /account/ for superuser must not render pending or unverified alerts."""
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('account:profile_complete'))
        
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Your profile is not verified yet.")
        self.assertNotContains(response, "Your account is not verified.")
        self.assertNotContains(response, "Approval Application is Pending")
        self.assertContains(response, "Verified")

    def test_04_profile_page_shows_unverified_for_normal_unapproved_user(self):
        """GET /account/ for unapproved normal user correctly displays unverified notice."""
        self.client.force_login(self.unapproved_user)
        response = self.client.get(reverse('account:profile_complete'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your profile is not verified yet.")
        self.assertContains(response, "Your account is not verified.")

    def test_05_profile_save_cannot_reset_superuser_to_pending(self):
        """POST to profile verification cannot demote superuser approval_status to 'p'."""
        self.client.force_login(self.superuser)
        
        # Post verification form submission
        response = self.client.post(
            reverse('account:profile_complete'),
            data={
                'requested_role': 'admin',
                'email': 'platform_admin@primesoul.edu.in',
                'approval_extra_note': 'Attempt to submit verification'
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.superuser.refresh_from_db()
        self.assertEqual(self.superuser.approval_status, ProfileApprovalStatusEnum.approved.value)
        self.assertTrue(self.superuser.is_superuser)

    def test_06_normal_user_verification_submit_sets_pending(self):
        """POST to profile verification for normal user correctly transitions status to 'p'."""
        self.client.force_login(self.unapproved_user)
        response = self.client.post(
            reverse('account:profile_complete'),
            data={
                'requested_role': 'TEACHER',
                'email': 'john@school.edu.in',
                'employee_or_student_id': 'T-001',
                'approval_extra_note': 'Please verify my account'
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.unapproved_user.refresh_from_db()
        self.assertEqual(self.unapproved_user.approval_status, ProfileApprovalStatusEnum.pending.value)

    def test_07_superuser_without_institute_redirects_to_onboarding(self):
        """Dashboard access for superuser with no institute/school must redirect to /institute/onboarding/."""
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('account:dashboard'))

        # Must redirect to institute:onboarding_step1
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('institute:onboarding_step1'))
