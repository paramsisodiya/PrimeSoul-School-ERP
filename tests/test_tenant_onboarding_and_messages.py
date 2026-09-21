"""
Tests for deterministic InstituteProfile onboarding to tenants.School bridging,
tenant context resolution, normal user isolation, and global message rendering.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from django_school_management.institute.models import InstituteProfile
from django_school_management.tenants.models import School, Domain, Subscription
from django_school_management.tenants.services import sync_institute_to_school_tenant
from django_school_management.accounts.constants import ProfileApprovalStatusEnum

User = get_user_model()


@override_settings(
    ALLOWED_HOSTS=['*'],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class TenantOnboardingAndMessagesTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Platform Superuser
        self.superuser = User.objects.create_superuser(
            username="super_admin_test",
            email="super_admin_test@primesoul.edu.in",
            password="Password123!"
        )

        # 2. School Admin User
        self.school_admin = User.objects.create_user(
            username="school_admin_test",
            email="school_admin_test@primesoul.edu.in",
            password="Password123!",
            approval_status=ProfileApprovalStatusEnum.approved.value,
            requested_role="SCHOOL_ADMIN"
        )

    def test_01_sync_institute_to_school_tenant_creates_tenant_and_domain(self):
        """sync_institute_to_school_tenant creates School, Domain, Subscription and links user."""
        inst = InstituteProfile.objects.create(
            name="PrimeSoul Higher Secondary School",
            country="India",
            active=True,
            onboarding_completed=True
        )

        school = sync_institute_to_school_tenant(inst, user=self.school_admin)
        
        self.assertIsNotNone(school)
        self.assertEqual(school.name, "PrimeSoul Higher Secondary School")
        self.assertTrue(school.is_active)
        self.assertTrue(school.onboarding_completed)

        # Domain verification
        domain = Domain.objects.filter(school=school).first()
        self.assertIsNotNone(domain)
        self.assertTrue(domain.is_primary)

        # Subscription verification
        subscription = Subscription.objects.filter(school=school).first()
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.status, "active")

        # User linkage
        self.school_admin.refresh_from_db()
        self.assertEqual(self.school_admin.school, school)

    def test_02_sync_institute_to_school_tenant_is_idempotent(self):
        """Repeated calls to sync_institute_to_school_tenant do not create duplicate records."""
        inst = InstituteProfile.objects.create(
            name="St. Xavier's International Academy",
            country="India",
            active=True,
            onboarding_completed=True
        )

        # First sync
        school1 = sync_institute_to_school_tenant(inst, user=self.school_admin)
        school_count_1 = School.objects.count()
        domain_count_1 = Domain.objects.count()
        sub_count_1 = Subscription.objects.count()

        # Second sync
        school2 = sync_institute_to_school_tenant(inst, user=self.school_admin)
        school_count_2 = School.objects.count()
        domain_count_2 = Domain.objects.count()
        sub_count_2 = Subscription.objects.count()

        self.assertEqual(school1.id, school2.id)
        self.assertEqual(school_count_1, school_count_2)
        self.assertEqual(domain_count_1, domain_count_2)
        self.assertEqual(sub_count_1, sub_count_2)

    def test_03_onboarding_step1_bridges_to_tenant_school(self):
        """Completing onboarding Step 1 deterministically provisions and binds a School tenant."""
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse('institute:onboarding_step1'),
            data={
                'name': 'Delhi Model Public School',
                'country': 'IN',
                'motto': 'Excellence in Education',
                'institute_type': 'school'
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        # Verify School tenant exists
        school = School.objects.filter(name='Delhi Model Public School').first()
        self.assertIsNotNone(school)
        self.assertTrue(school.is_active)

        # Verify superuser is linked to this school
        self.superuser.refresh_from_db()
        self.assertEqual(self.superuser.school, school)

    def test_04_dashboard_loads_resolved_school_and_tenant_active_badge(self):
        """Dashboard renders dynamic tenant badge and resolved school name without missing tenant error."""
        # Create an onboarded institute & tenant
        inst = InstituteProfile.objects.create(
            name="Greenwood High Global Campus",
            country="India",
            active=True,
            onboarding_completed=True
        )
        school = sync_institute_to_school_tenant(inst, user=self.superuser)

        self.client.force_login(self.superuser)
        response = self.client.get(reverse('account:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Greenwood High Global Campus")
        self.assertContains(response, "Tenant Active")
        self.assertNotContains(response, "No active school tenant context found.")

    def test_05_global_messages_toast_renders_with_styling(self):
        """Global toast notification partial renders messages without pushing content."""
        inst = InstituteProfile.objects.create(
            name="Delhi Public School",
            country="India",
            active=True,
            onboarding_completed=True
        )
        sync_institute_to_school_tenant(inst, user=self.superuser)

        self.client.force_login(self.superuser)
        
        # Make a request that generates a message (e.g. step 1 or adding message to session)
        # Using client session to store message
        session = self.client.session
        from django.contrib.messages.storage.fallback import FallbackStorage
        # Test rendering via a view that adds message or passing messages
        response = self.client.post(
            reverse('institute:onboarding_step1'),
            data={
                'name': 'Delhi Public School Updated',
                'country': 'IN',
                'institute_type': 'school'
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "primesoul-toast-container")
        self.assertContains(response, "primesoul-toast-success")

    def test_06_tenant_isolation_between_distinct_schools(self):
        """Users linked to School A have request.user.school pointing to School A, not School B."""
        inst_a = InstituteProfile.objects.create(name="School Alpha", country="India", active=True, onboarding_completed=True)
        school_a = sync_institute_to_school_tenant(inst_a, user=self.school_admin)

        other_user = User.objects.create_user(
            username="other_admin",
            email="other@primesoul.edu.in",
            password="Password123!",
            approval_status=ProfileApprovalStatusEnum.approved.value,
        )
        inst_b = InstituteProfile.objects.create(name="School Beta", country="India", active=False, onboarding_completed=True)
        school_b = sync_institute_to_school_tenant(inst_b, user=other_user)

        self.school_admin.refresh_from_db()
        other_user.refresh_from_db()

        self.assertEqual(self.school_admin.school, school_a)
        self.assertEqual(other_user.school, school_b)
        self.assertNotEqual(self.school_admin.school, other_user.school)
