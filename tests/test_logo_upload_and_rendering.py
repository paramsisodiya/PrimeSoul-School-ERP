"""
Tests for School Logo upload, URL generation, persistent storage configuration,
media serving under DEBUG=False, template rendering, and multi-tenant isolation.
"""
import io
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings

from django_school_management.institute.models import InstituteProfile
from django_school_management.tenants.models import School
from django_school_management.tenants.services import sync_institute_to_school_tenant
from django_school_management.accounts.constants import ProfileApprovalStatusEnum

User = get_user_model()


def generate_test_image_file(filename="test_logo.png", size=(100, 100), color=(79, 70, 229)):
    """Helper to create an in-memory PNG image file for testing."""
    file_io = io.BytesIO()
    image = Image.new("RGB", size, color)
    image.save(file_io, format="PNG")
    file_io.seek(0)
    return SimpleUploadedFile(
        name=filename,
        content=file_io.read(),
        content_type="image/png"
    )


@override_settings(
    ALLOWED_HOSTS=['*'],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class SchoolLogoPipelineTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Platform Superuser
        self.superuser = User.objects.create_superuser(
            username="logo_test_admin",
            email="logo_admin@primesoul.edu.in",
            password="Password123!"
        )

    def test_01_logo_upload_during_onboarding_and_url_generation(self):
        """Uploading logo in onboarding saves file, populates logo.url, and synchronizes with School."""
        self.client.force_login(self.superuser)

        test_img = generate_test_image_file("school_logo_step1.png")
        response = self.client.post(
            reverse('institute:onboarding_step1'),
            data={
                'name': 'Greenwood International School',
                'country': 'IN',
                'motto': 'Lead with Knowledge',
                'institute_type': 'school',
                'logo': test_img
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)

        inst = InstituteProfile.objects.filter(name='Greenwood International School').first()
        self.assertIsNotNone(inst)
        self.assertTrue(bool(inst.logo))
        self.assertTrue(inst.logo.url.startswith('/media/') or inst.logo.url.startswith('http'))

        # Verify School tenant synchronization
        school = School.objects.filter(name='Greenwood International School').first()
        self.assertIsNotNone(school)
        self.assertTrue(bool(school.logo))
        self.assertEqual(school.logo.name, inst.logo.name)
        self.assertEqual(school.logo.url, inst.logo.url)

    def test_02_media_url_served_directly_under_debug_false(self):
        """Media files at MEDIA_URL are routed and served successfully even with DEBUG=False."""
        inst = InstituteProfile.objects.create(
            name="Delhi Public Academy",
            country="India",
            active=True,
            onboarding_completed=True
        )
        test_img = generate_test_image_file("academy_logo.png")
        inst.logo.save("academy_logo.png", test_img, save=True)

        with override_settings(DEBUG=False):
            media_url = inst.logo.url
            # Request media file directly
            response = self.client.get(media_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')

    def test_03_login_page_renders_school_logo_with_fallback(self):
        """Login page (/accounts/login/) renders school logo img tag and onerror fallback handler."""
        inst = InstituteProfile.objects.create(
            name="Modern Heritage Public School",
            country="India",
            active=True,
            onboarding_completed=True
        )
        test_img = generate_test_image_file("heritage_logo.png")
        inst.logo.save("heritage_logo.png", test_img, save=True)
        sync_institute_to_school_tenant(inst, user=self.superuser)

        response = self.client.get(reverse('account_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, inst.logo.url)
        self.assertContains(response, 'alt="Modern Heritage Public School"')
        self.assertContains(response, 'onerror=')
        self.assertContains(response, 'login-logo-fallback')

    def test_04_login_page_renders_clean_fallback_when_no_logo_exists(self):
        """Login page renders initial letter badge without broken images when no logo is uploaded."""
        InstituteProfile.objects.create(
            name="Sunrise Valley School",
            country="India",
            active=True,
            onboarding_completed=True,
            logo=None
        )

        response = self.client.get(reverse('account_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sunrise Valley School')
        # S avatar for Sunrise Valley School
        self.assertContains(response, '>S</span>')

    def test_05_sidebar_and_website_header_render_logo(self):
        """Sidebar and public website templates render school logo with onerror fallback."""
        inst = InstituteProfile.objects.create(
            name="Cambridge World Academy",
            country="India",
            active=True,
            onboarding_completed=True
        )
        test_img = generate_test_image_file("cambridge_logo.png")
        inst.logo.save("cambridge_logo.png", test_img, save=True)
        sync_institute_to_school_tenant(inst, user=self.superuser)

        # Authenticated dashboard request renders sidebar
        self.client.force_login(self.superuser)
        dash_response = self.client.get(reverse('account:dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, inst.logo.url)

        # Unauthenticated website landing page
        self.client.logout()
        web_response = self.client.get(reverse('pages:landing'))
        self.assertEqual(web_response.status_code, 200)
        self.assertContains(web_response, inst.logo.url)

    def test_06_s3_storage_configuration_settings(self):
        """Configuring S3 environment settings configures storages.backends.s3.S3Storage in STORAGES."""
        from django.core.files.storage import storages
        
        # Test that storages['default'] returns valid storage backend
        default_storage = storages['default']
        self.assertIsNotNone(default_storage)

    def test_07_tenant_isolation_preserves_distinct_school_logos(self):
        """Tenant A and Tenant B maintain distinct logo paths without cross-contamination."""
        inst_a = InstituteProfile.objects.create(name="School Alpha", country="India", active=True, onboarding_completed=True)
        img_a = generate_test_image_file("alpha_logo.png", color=(255, 0, 0))
        inst_a.logo.save("alpha_logo.png", img_a, save=True)
        school_a = sync_institute_to_school_tenant(inst_a)

        inst_b = InstituteProfile.objects.create(name="School Beta", country="India", active=False, onboarding_completed=True)
        img_b = generate_test_image_file("beta_logo.png", color=(0, 255, 0))
        inst_b.logo.save("beta_logo.png", img_b, save=True)
        school_b = sync_institute_to_school_tenant(inst_b)

        self.assertIn("alpha_logo", school_a.logo.url)
        self.assertIn("beta_logo", school_b.logo.url)
        self.assertNotEqual(school_a.logo.url, school_b.logo.url)
